<script>
  import { onMount } from 'svelte';
  import { apiRequest, formatDate } from '$lib/api';
  import { showToast } from '$lib/stores';

  let jobs = $state([]);
  let servers = $state([]);
  let loading = $state(true);
  let runningJobId = $state(null);

  // Modal State
  let showModal = $state(false);
  let isEditing = $state(false);
  let formId = $state(null);
  let formName = $state('');
  let formServerId = $state('');
  let formDatabaseName = $state('');
  let formCronExpr = $state('0 2 * * *');
  let formIsActive = $state(true);
  let formN1Daily = $state(7);
  let formN2Weekly = $state(4);
  let formN3Monthly = $state(12);

  // Frequency selector tab
  let frequencyPreset = $state('daily'); // 'daily', 'weekly', 'monthly', 'custom'
  let dailyHour = $state(2);
  let dailyMinute = $state(0);
  let weeklyDay = $state(0); // 0=Sunday
  let weeklyHour = $state(3);
  let monthlyDay = $state(1);
  let monthlyHour = $state(4);
  let customCronInput = $state('0 2 * * *');
  let submitting = $state(false);

  async function loadData() {
    try {
      const [jobsData, serversData] = await Promise.all([
        apiRequest('/jobs'),
        apiRequest('/servers'),
      ]);
      jobs = jobsData;
      servers = serversData;
    } catch (err) {
      showToast('Erreur chargement: ' + err.message, 'error');
    } finally {
      loading = false;
    }
  }

  function updateCronFromPreset() {
    if (frequencyPreset === 'daily') {
      formCronExpr = `${dailyMinute} ${dailyHour} * * *`;
    } else if (frequencyPreset === 'weekly') {
      formCronExpr = `0 ${weeklyHour} * * ${weeklyDay}`;
    } else if (frequencyPreset === 'monthly') {
      formCronExpr = `0 ${monthlyHour} ${monthlyDay} * *`;
    } else if (frequencyPreset === 'custom') {
      formCronExpr = customCronInput;
    }
  }

  function openCreateModal() {
    isEditing = false;
    formId = null;
    formName = '';
    formServerId = servers.length > 0 ? servers[0].id : '';
    formDatabaseName = '';
    frequencyPreset = 'daily';
    dailyHour = 2;
    dailyMinute = 0;
    formN1Daily = 7;
    formN2Weekly = 4;
    formN3Monthly = 12;
    formIsActive = true;
    updateCronFromPreset();
    showModal = true;
  }

  function openEditModal(job) {
    isEditing = true;
    formId = job.id;
    formName = job.name;
    formServerId = job.server_id;
    formDatabaseName = job.database_name;
    formCronExpr = job.cron_expression;
    customCronInput = job.cron_expression;
    frequencyPreset = 'custom'; // Default to custom so existing expression is preserved
    formIsActive = job.is_active;
    formN1Daily = job.retention_daily;
    formN2Weekly = job.retention_weekly;
    formN3Monthly = job.retention_monthly;
    showModal = true;
  }

  async function handleSaveJob(e) {
    e.preventDefault();
    updateCronFromPreset();

    if (!formServerId) {
      showToast('Veuillez sélectionner un serveur', 'error');
      return;
    }

    submitting = true;
    const payload = {
      name: formName,
      server_id: Number(formServerId),
      database_name: formDatabaseName,
      cron_expression: formCronExpr.trim(),
      is_active: formIsActive,
      retention_daily: Number(formN1Daily),
      retention_weekly: Number(formN2Weekly),
      retention_monthly: Number(formN3Monthly),
    };

    try {
      if (isEditing) {
        await apiRequest(`/jobs/${formId}`, { method: 'PUT', body: payload });
        showToast(`Tâche '${formName}' mise à jour et Crontab synchronisé`, 'success');
      } else {
        await apiRequest('/jobs', { method: 'POST', body: payload });
        showToast(`Tâche '${formName}' créée et Crontab synchronisé`, 'success');
      }
      showModal = false;
      await loadData();
    } catch (err) {
      showToast('Erreur: ' + err.message, 'error');
    } finally {
      submitting = false;
    }
  }

  async function handleToggleJob(job) {
    try {
      const updated = await apiRequest(`/jobs/${job.id}/toggle`, { method: 'PATCH' });
      job.is_active = updated.is_active;
      showToast(`Tâche '${job.name}' ${updated.is_active ? 'activée' : 'désactivée'} (Crontab mis à jour)`, 'info');
    } catch (err) {
      showToast('Erreur: ' + err.message, 'error');
    }
  }

  async function handleDeleteJob(job) {
    if (!confirm(`Supprimer la tâche '${job.name}' ? Les sauvegardes existantes sur disque seront conservées.`)) {
      return;
    }
    try {
      await apiRequest(`/jobs/${job.id}`, { method: 'DELETE' });
      showToast(`Tâche supprimée et /etc/cron.d/cronstash actualisé`, 'info');
      await loadData();
    } catch (err) {
      showToast('Erreur suppression: ' + err.message, 'error');
    }
  }

  async function handleRunNow(job) {
    runningJobId = job.id;
    showToast(`Lancement de la sauvegarde pour '${job.name}'...`, 'info', 2000);

    try {
      const log = await apiRequest(`/jobs/${job.id}/run-now`, { method: 'POST' });
      if (log.status === 'success') {
        showToast(`Sauvegarde de '${job.name}' réussie ! (${log.duration_seconds}s)`, 'success');
      } else {
        showToast(`Échec de sauvegarde pour '${job.name}': ${log.error_message}`, 'error', 6000);
      }
      await loadData();
    } catch (err) {
      showToast(`Erreur d'exécution: ${err.message}`, 'error');
    } finally {
      runningJobId = null;
    }
  }

  onMount(() => {
    loadData();
  });
</script>

<div class="p-6 md:p-10 max-w-7xl mx-auto space-y-8">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <h1 class="text-2xl md:text-3xl font-bold tracking-tight text-white flex items-center gap-3">
        Tâches de Sauvegarde Planifiées
      </h1>
      <p class="text-sm text-slate-400 mt-1">
        Gestion des fréquences d'exécution et de la rétention GFS avec écriture dans <span class="font-mono text-indigo-400">/etc/cron.d/cronstash</span>
      </p>
    </div>

    <button
      onclick={openCreateModal}
      class="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20 transition"
    >
      <span>➕</span>
      <span>Créer une tâche</span>
    </button>
  </div>

  {#if loading}
    <div class="py-20 flex justify-center text-slate-400">
      <div class="w-8 h-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin"></div>
    </div>
  {:else if jobs.length === 0}
    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center shadow-sm">
      <span class="text-4xl block mb-3">⏱️</span>
      <h3 class="text-lg font-semibold text-white">Aucune tâche planifiée</h3>
      <p class="text-sm text-slate-400 max-w-md mx-auto mt-1 mb-6">
        Configurez une sauvegarde automatique pour une base PostgreSQL ou un dépôt RDF4J avec votre politique de rétention GFS.
      </p>
      <button
        onclick={openCreateModal}
        class="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition"
      >
        <span>➕ Créer une tâche</span>
      </button>
    </div>
  {:else}
    <!-- Jobs List -->
    <div class="space-y-4">
      {#each jobs as job}
        <div class="bg-slate-900 border border-slate-800 hover:border-slate-700/80 rounded-2xl p-5 shadow-sm transition flex flex-col lg:flex-row lg:items-center justify-between gap-5">
          <!-- Left info -->
          <div class="flex items-start gap-4">
            <!-- Active Toggle -->
            <button
              onclick={() => handleToggleJob(job)}
              title={job.is_active ? 'Désactiver la tâche' : 'Activer la tâche'}
              class="mt-1 relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none {
                job.is_active ? 'bg-indigo-600' : 'bg-slate-700'
              }"
            >
              <span
                class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out {
                  job.is_active ? 'translate-x-5' : 'translate-x-0'
                }"
              ></span>
            </button>

            <div>
              <div class="flex flex-wrap items-center gap-2.5">
                <h3 class="text-base font-bold text-white">{job.name}</h3>
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium {
                  job.server_type === 'postgresql' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                }">
                  {job.server_type}
                </span>
                <span class="text-xs text-slate-400">
                  Serveur: <strong class="text-slate-200">{job.server_name}</strong> • Base: <strong class="text-slate-200 font-mono">{job.database_name}</strong>
                </span>
              </div>

              <!-- Cron info & GFS Badges -->
              <div class="mt-2.5 flex flex-wrap items-center gap-3 text-xs">
                <div class="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-950 border border-slate-800 font-mono text-slate-300">
                  <span>⏱️</span>
                  <span>{job.cron_expression}</span>
                </div>

                <!-- GFS Retention Badges -->
                <div class="flex items-center gap-1.5 bg-slate-950/80 px-2.5 py-1 rounded-md border border-slate-800 text-[11px]">
                  <span class="text-slate-400">Rétention GFS :</span>
                  <span class="text-emerald-400 font-semibold" title="Son (Quotidien)">N1: {job.retention_daily}j</span>
                  <span class="text-slate-600">•</span>
                  <span class="text-sky-400 font-semibold" title="Father (Hebdomadaire)">N2: {job.retention_weekly}sem</span>
                  <span class="text-slate-600">•</span>
                  <span class="text-purple-400 font-semibold" title="Grandfather (Mensuel)">N3: {job.retention_monthly}m</span>
                </div>

                {#if job.last_run_at}
                  <span class="text-slate-400">
                    Dernière exécution : <span class="text-slate-300">{formatDate(job.last_run_at)}</span>
                  </span>
                {/if}

                {#if job.next_run_at}
                  <span class="text-slate-400">
                    Prochaine : <span class="text-indigo-300 font-medium">{formatDate(job.next_run_at)}</span>
                  </span>
                {/if}
              </div>
            </div>
          </div>

          <!-- Right actions -->
          <div class="flex items-center gap-2 shrink-0 self-end lg:self-center">
            <button
              onclick={() => handleRunNow(job)}
              disabled={runningJobId === job.id}
              class="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 disabled:opacity-50 text-white shadow-sm transition"
            >
              {#if runningJobId === job.id}
                <div class="w-3.5 h-3.5 rounded-full border-2 border-white border-t-transparent animate-spin"></div>
                <span>Exécution...</span>
              {:else}
                <span>⚡ Sauvegarder maintenant</span>
              {/if}
            </button>

            <button
              onclick={() => openEditModal(job)}
              title="Modifier"
              class="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition text-sm"
            >
              ✏️
            </button>

            <button
              onclick={() => handleDeleteJob(job)}
              title="Supprimer"
              class="p-2 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-xl transition text-sm"
            >
              🗑️
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <!-- Add/Edit Modal -->
  {#if showModal}
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
      <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl flex flex-col max-h-[90vh] overflow-y-auto">
        <div class="flex items-center justify-between pb-4 border-b border-slate-800">
          <h3 class="text-lg font-bold text-white">
            {isEditing ? 'Modifier la tâche de sauvegarde' : 'Nouvelle tâche de sauvegarde'}
          </h3>
          <button onclick={() => (showModal = false)} class="text-slate-400 hover:text-white p-1 rounded-lg">
            ✕
          </button>
        </div>

        <form onsubmit={handleSaveJob} class="mt-5 space-y-5">
          <!-- Server & Database selection -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label for="modal-server" class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Serveur Cible
              </label>
              <select
                id="modal-server"
                bind:value={formServerId}
                required
                class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none"
              >
                {#each servers as s}
                  <option value={s.id}>{s.name} ({s.server_type})</option>
                {/each}
              </select>
            </div>

            <div>
              <label for="modal-db-name" class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Base de données / Dépôt RDF4J
              </label>
              <input
                id="modal-db-name"
                type="text"
                bind:value={formDatabaseName}
                required
                placeholder="ex: app_production"
                class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none font-mono"
              />
            </div>
          </div>

          <div>
            <label for="modal-job-name" class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Nom de la tâche
            </label>
            <input
              id="modal-job-name"
              type="text"
              bind:value={formName}
              required
              placeholder="ex: Sauvegarde Quotidienne Clients"
              class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none"
            />
          </div>

          <!-- VISUAL FREQUENCY SELECTOR -->
          <div class="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
            <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400">
              Fréquence d'exécution (Cron)
            </label>

            <!-- Preset tabs -->
            <div class="grid grid-cols-4 gap-2">
              <button
                type="button"
                onclick={() => { frequencyPreset = 'daily'; updateCronFromPreset(); }}
                class="py-2 px-2 text-xs font-semibold rounded-lg border transition text-center {
                  frequencyPreset === 'daily'
                    ? 'bg-indigo-600 border-indigo-500 text-white'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                }"
              >
                ☀️ Quotidien
              </button>

              <button
                type="button"
                onclick={() => { frequencyPreset = 'weekly'; updateCronFromPreset(); }}
                class="py-2 px-2 text-xs font-semibold rounded-lg border transition text-center {
                  frequencyPreset === 'weekly'
                    ? 'bg-indigo-600 border-indigo-500 text-white'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                }"
              >
                📅 Hebdo
              </button>

              <button
                type="button"
                onclick={() => { frequencyPreset = 'monthly'; updateCronFromPreset(); }}
                class="py-2 px-2 text-xs font-semibold rounded-lg border transition text-center {
                  frequencyPreset === 'monthly'
                    ? 'bg-indigo-600 border-indigo-500 text-white'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                }"
              >
                🌕 Mensuel
              </button>

              <button
                type="button"
                onclick={() => { frequencyPreset = 'custom'; updateCronFromPreset(); }}
                class="py-2 px-2 text-xs font-semibold rounded-lg border transition text-center {
                  frequencyPreset === 'custom'
                    ? 'bg-indigo-600 border-indigo-500 text-white'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                }"
              >
                ⚙️ Manuel
              </button>
            </div>

            <!-- Tab content -->
            {#if frequencyPreset === 'daily'}
              <div class="flex items-center gap-3 pt-2">
                <span class="text-xs text-slate-400">Tous les jours à :</span>
                <input
                  type="number"
                  min="0"
                  max="23"
                  bind:value={dailyHour}
                  oninput={updateCronFromPreset}
                  class="w-16 bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-sm text-center text-white"
                />
                <span class="text-slate-500">:</span>
                <input
                  type="number"
                  min="0"
                  max="59"
                  bind:value={dailyMinute}
                  oninput={updateCronFromPreset}
                  class="w-16 bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-sm text-center text-white"
                />
                <span class="text-xs text-slate-500">h (UTC)</span>
              </div>
            {:else if frequencyPreset === 'weekly'}
              <div class="flex items-center gap-3 pt-2">
                <span class="text-xs text-slate-400">Chaque :</span>
                <select
                  bind:value={weeklyDay}
                  onchange={updateCronFromPreset}
                  class="bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white"
                >
                  <option value={0}>Dimanche</option>
                  <option value={1}>Lundi</option>
                  <option value={2}>Mardi</option>
                  <option value={3}>Mercredi</option>
                  <option value={4}>Jeudi</option>
                  <option value={5}>Vendredi</option>
                  <option value={6}>Samedi</option>
                </select>
                <span class="text-xs text-slate-400">à</span>
                <input
                  type="number"
                  min="0"
                  max="23"
                  bind:value={weeklyHour}
                  oninput={updateCronFromPreset}
                  class="w-16 bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-sm text-center text-white"
                />
                <span class="text-xs text-slate-500">h:00 UTC</span>
              </div>
            {:else if frequencyPreset === 'monthly'}
              <div class="flex items-center gap-3 pt-2">
                <span class="text-xs text-slate-400">Le</span>
                <input
                  type="number"
                  min="1"
                  max="28"
                  bind:value={monthlyDay}
                  oninput={updateCronFromPreset}
                  class="w-14 bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-sm text-center text-white"
                />
                <span class="text-xs text-slate-400">du mois à</span>
                <input
                  type="number"
                  min="0"
                  max="23"
                  bind:value={monthlyHour}
                  oninput={updateCronFromPreset}
                  class="w-16 bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-sm text-center text-white"
                />
                <span class="text-xs text-slate-500">h:00 UTC</span>
              </div>
            {:else}
              <div class="pt-2">
                <input
                  type="text"
                  bind:value={customCronInput}
                  oninput={updateCronFromPreset}
                  placeholder="* * * * *"
                  class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm font-mono text-white outline-none"
                />
                <span class="text-[11px] text-slate-500 block mt-1">Syntaxe standard cron à 5 champs (minute heure jour mois jour_semaine)</span>
              </div>
            {/if}

            <div class="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono">
              <span class="text-slate-400">Expression Cron finale :</span>
              <span class="text-indigo-400 font-bold bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">{formCronExpr}</span>
            </div>
          </div>

          <!-- GFS RETENTION POLICY CONTROLS -->
          <div class="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-4">
            <div class="flex items-center justify-between">
              <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400">
                Politique de Rétention GFS
              </label>
              <span class="text-[11px] text-slate-500">Grandfather-Father-Son</span>
            </div>

            <!-- N1 (Daily / Son) -->
            <div>
              <div class="flex justify-between text-xs mb-1">
                <span class="text-emerald-400 font-medium">N1 - Fils (Daily) :</span>
                <span class="text-white font-bold">{formN1Daily} jours</span>
              </div>
              <input
                type="range"
                min="1"
                max="90"
                bind:value={formN1Daily}
                class="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-emerald-500"
              />
              <span class="text-[10px] text-slate-500">Conserve les {formN1Daily} sauvegardes quotidiennes les plus récentes.</span>
            </div>

            <!-- N2 (Weekly / Father) -->
            <div>
              <div class="flex justify-between text-xs mb-1">
                <span class="text-sky-400 font-medium">N2 - Père (Weekly) :</span>
                <span class="text-white font-bold">{formN2Weekly} semaines</span>
              </div>
              <input
                type="range"
                min="0"
                max="52"
                bind:value={formN2Weekly}
                class="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-sky-500"
              />
              <span class="text-[10px] text-slate-500">Conserve {formN2Weekly} sauvegardes hebdomadaires (prises le dimanche).</span>
            </div>

            <!-- N3 (Monthly / Grandfather) -->
            <div>
              <div class="flex justify-between text-xs mb-1">
                <span class="text-purple-400 font-medium">N3 - Grand-père (Monthly) :</span>
                <span class="text-white font-bold">{formN3Monthly} mois</span>
              </div>
              <input
                type="range"
                min="0"
                max="60"
                bind:value={formN3Monthly}
                class="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-purple-500"
              />
              <span class="text-[10px] text-slate-500">Conserve {formN3Monthly} sauvegardes mensuelles (prises le 1er du mois).</span>
            </div>
          </div>

          <!-- Submit Buttons -->
          <div class="pt-4 border-t border-slate-800 flex items-center justify-end gap-3">
            <button
              type="button"
              onclick={() => (showModal = false)}
              class="px-4 py-2.5 rounded-xl text-sm font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
            >
              Annuler
            </button>
            <button
              type="submit"
              disabled={submitting}
              class="px-5 py-2.5 rounded-xl text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition flex items-center gap-2"
            >
              {#if submitting}
                <div class="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin"></div>
              {/if}
              <span>{isEditing ? 'Mettre à jour la tâche' : 'Planifier la tâche'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  {/if}
</div>
