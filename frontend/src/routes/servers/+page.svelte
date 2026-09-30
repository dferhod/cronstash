<script>
  import { onMount } from 'svelte';
  import { apiRequest } from '$lib/api';
  import { showToast } from '$lib/stores';

  let servers = $state([]);
  let loading = $state(true);

  // Add / Edit Modal state
  let showModal = $state(false);
  let isEditing = $state(false);
  let formId = $state(null);
  let formName = $state('');
  let formType = $state('postgresql');
  let formHost = $state('127.0.0.1');
  let formPort = $state(5432);
  let formUsername = $state('postgres');
  let formPassword = $state('');
  let formExtraParams = $state('');
  let submitting = $state(false);

  // Discovery state
  let showDiscoveryModal = $state(false);
  let discovering = $state(false);
  let discoveryTargetServer = $state(null);
  let discoveredDatabases = $state([]);
  let selectedDbNames = $state([]);
  let creatingBatchJobs = $state(false);

  async function loadServers() {
    try {
      servers = await apiRequest('/servers');
    } catch (err) {
      showToast('Erreur chargement serveurs: ' + err.message, 'error');
    } finally {
      loading = false;
    }
  }

  function openCreateModal() {
    isEditing = false;
    formId = null;
    formName = '';
    formType = 'postgresql';
    formHost = '127.0.0.1';
    formPort = 5432;
    formUsername = 'postgres';
    formPassword = '';
    formExtraParams = '';
    showModal = true;
  }

  function handleTypeChange() {
    if (formType === 'postgresql') {
      if (formPort === 8080) formPort = 5432;
      if (!formUsername) formUsername = 'postgres';
    } else {
      if (formPort === 5432) formPort = 8080;
    }
  }

  function openEditModal(srv) {
    isEditing = true;
    formId = srv.id;
    formName = srv.name;
    formType = srv.server_type;
    formHost = srv.host;
    formPort = srv.port;
    formUsername = srv.username || '';
    formPassword = '';
    formExtraParams = srv.extra_params || '';
    showModal = true;
  }

  async function handleSaveServer(e) {
    e.preventDefault();
    submitting = true;

    const payload = {
      name: formName,
      server_type: formType,
      host: formHost,
      port: Number(formPort),
      username: formUsername || null,
      extra_params: formExtraParams || null,
    };

    if (formPassword) {
      payload.password = formPassword;
    }

    try {
      if (isEditing) {
        await apiRequest(`/servers/${formId}`, { method: 'PUT', body: payload });
        showToast(`Serveur '${formName}' mis à jour`, 'success');
      } else {
        await apiRequest('/servers', { method: 'POST', body: payload });
        showToast(`Serveur '${formName}' ajouté avec succès`, 'success');
      }
      showModal = false;
      await loadServers();
    } catch (err) {
      showToast('Erreur: ' + err.message, 'error');
    } finally {
      submitting = false;
    }
  }

  async function handleDeleteServer(srv) {
    if (!confirm(`Supprimer définitivement le serveur '${srv.name}' ? Tous les jobs et historiques associés seront également supprimés.`)) {
      return;
    }
    try {
      await apiRequest(`/servers/${srv.id}`, { method: 'DELETE' });
      showToast(`Serveur '${srv.name}' supprimé`, 'info');
      await loadServers();
    } catch (err) {
      showToast('Erreur suppression: ' + err.message, 'error');
    }
  }

  // DISCOVERY
  async function triggerDiscovery(srv) {
    discoveryTargetServer = srv;
    discovering = true;
    showDiscoveryModal = true;
    discoveredDatabases = [];
    selectedDbNames = [];

    try {
      const res = await apiRequest(`/servers/${srv.id}/discover`, { method: 'POST' });
      discoveredDatabases = res.databases || [];
      // Auto-select unmonitored databases
      selectedDbNames = discoveredDatabases.filter(d => !d.already_monitored).map(d => d.name);
    } catch (err) {
      showToast(`Échec de découverte: ${err.message}`, 'error');
    } finally {
      discovering = false;
    }
  }

  function toggleDbSelection(name) {
    if (selectedDbNames.includes(name)) {
      selectedDbNames = selectedDbNames.filter(n => n !== name);
    } else {
      selectedDbNames = [...selectedDbNames, name];
    }
  }

  async function handleCreateJobsFromDiscovery() {
    if (selectedDbNames.length === 0) {
      showToast('Veuillez cocher au moins une base', 'info');
      return;
    }

    creatingBatchJobs = true;
    let createdCount = 0;

    for (const dbName of selectedDbNames) {
      try {
        await apiRequest('/jobs', {
          method: 'POST',
          body: {
            name: `Sauvegarde ${dbName}`,
            server_id: discoveryTargetServer.id,
            database_name: dbName,
            cron_expression: '0 2 * * *', // Daily 02:00
            is_active: true,
            retention_daily: 7,
            retention_weekly: 4,
            retention_monthly: 12,
          }
        });
        createdCount++;
      } catch (e) {
        console.error(`Erreur création job pour ${dbName}:`, e);
      }
    }

    creatingBatchJobs = false;
    showDiscoveryModal = false;
    showToast(`${createdCount} tâche(s) de sauvegarde créée(s) et crontab mis à jour !`, 'success');
  }

  onMount(() => {
    loadServers();
  });
</script>

<div class="p-6 md:p-10 max-w-7xl mx-auto space-y-8">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <h1 class="text-2xl md:text-3xl font-bold tracking-tight text-white flex items-center gap-3">
        Serveurs de Bases de Données
      </h1>
      <p class="text-sm text-slate-400 mt-1">Connexion PostgreSQL 18 & clusters RDF4J avec découverte dynamique</p>
    </div>

    <button
      onclick={openCreateModal}
      class="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20 transition"
    >
      <span>➕</span>
      <span>Ajouter un serveur</span>
    </button>
  </div>

  {#if loading}
    <div class="py-20 flex justify-center text-slate-400">
      <div class="w-8 h-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin"></div>
    </div>
  {:else if servers.length === 0}
    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center shadow-sm">
      <span class="text-4xl block mb-3">🖥️</span>
      <h3 class="text-lg font-semibold text-white">Aucun serveur enregistré</h3>
      <p class="text-sm text-slate-400 max-w-md mx-auto mt-1 mb-6">
        Ajoutez votre première instance PostgreSQL 18 ou serveur RDF4J pour lancer la découverte des bases.
      </p>
      <button
        onclick={openCreateModal}
        class="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition"
      >
        <span>➕ Ajouter un serveur</span>
      </button>
    </div>
  {:else}
    <!-- Servers Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {#each servers as srv}
        <div class="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-6 shadow-sm flex flex-col justify-between transition">
          <div>
            <!-- Server Card Header -->
            <div class="flex items-start justify-between">
              <div>
                <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold uppercase tracking-wider font-mono {
                  srv.server_type === 'postgresql' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                }">
                  {srv.server_type === 'postgresql' ? '🐘 PostgreSQL 18' : '🌐 RDF4J'}
                </span>
                <h3 class="text-lg font-bold text-white mt-2.5">{srv.name}</h3>
              </div>

              <div class="flex items-center gap-1">
                <button
                  onclick={() => openEditModal(srv)}
                  title="Modifier"
                  class="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition"
                >
                  ✏️
                </button>
                <button
                  onclick={() => handleDeleteServer(srv)}
                  title="Supprimer"
                  class="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition"
                >
                  🗑️
                </button>
              </div>
            </div>

            <!-- Server Details -->
            <div class="mt-4 space-y-2 text-xs">
              <div class="flex items-center justify-between py-1.5 border-b border-slate-800/80">
                <span class="text-slate-400">Hôte :</span>
                <span class="font-mono text-slate-200">{srv.host}</span>
              </div>
              <div class="flex items-center justify-between py-1.5 border-b border-slate-800/80">
                <span class="text-slate-400">Port :</span>
                <span class="font-mono text-slate-200">{srv.port}</span>
              </div>
              <div class="flex items-center justify-between py-1.5 border-b border-slate-800/80">
                <span class="text-slate-400">Utilisateur :</span>
                <span class="font-mono text-slate-200">{srv.username || 'Par défaut'}</span>
              </div>
              <div class="flex items-center justify-between py-1.5">
                <span class="text-slate-400">Authentification :</span>
                <span class="text-slate-300">{srv.has_password ? '🔑 Protégé par mot de passe' : 'Sans mot de passe'}</span>
              </div>
            </div>
          </div>

          <!-- Discovery Action Button -->
          <div class="mt-6 pt-4 border-t border-slate-800">
            <button
              onclick={() => triggerDiscovery(srv)}
              class="w-full py-2.5 px-3 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-indigo-600 text-slate-200 hover:text-white transition flex items-center justify-center gap-2 group"
            >
              <span>🔍</span>
              <span>Découvrir les bases</span>
              <span class="text-slate-500 group-hover:text-white transition">→</span>
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <!-- Add/Edit Modal -->
  {#if showModal}
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl">
        <div class="flex items-center justify-between pb-4 border-b border-slate-800">
          <h3 class="text-lg font-bold text-white">
            {isEditing ? 'Modifier le serveur' : 'Nouveau serveur de bases'}
          </h3>
          <button onclick={() => (showModal = false)} class="text-slate-400 hover:text-white p-1 rounded-lg">
            ✕
          </button>
        </div>

        <form onsubmit={handleSaveServer} class="mt-5 space-y-4">
          <div>
            <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Type de Serveur
            </label>
            <div class="grid grid-cols-2 gap-3">
              <label class="flex items-center gap-2.5 p-3 rounded-xl border cursor-pointer transition {
                formType === 'postgresql' ? 'bg-indigo-500/10 border-indigo-500 text-white' : 'bg-slate-950 border-slate-800 text-slate-400'
              }">
                <input type="radio" name="server_type" value="postgresql" bind:group={formType} onchange={handleTypeChange} class="hidden" />
                <span class="text-lg">🐘</span>
                <span class="text-xs font-semibold">PostgreSQL 18</span>
              </label>

              <label class="flex items-center gap-2.5 p-3 rounded-xl border cursor-pointer transition {
                formType === 'rdf4j' ? 'bg-indigo-500/10 border-indigo-500 text-white' : 'bg-slate-950 border-slate-800 text-slate-400'
              }">
                <input type="radio" name="server_type" value="rdf4j" bind:group={formType} onchange={handleTypeChange} class="hidden" />
                <span class="text-lg">🌐</span>
                <span class="text-xs font-semibold">RDF4J Triplestore</span>
              </label>
            </div>
          </div>

          <div>
            <label for="form-name" class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Nom d'affichage
            </label>
            <input
              id="form-name"
              type="text"
              bind:value={formName}
              required
              placeholder="ex: pg-cluster-prod ou rdf4j-main"
              class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none"
            />
          </div>

          <div class="grid grid-cols-3 gap-3">
            <div class="col-span-2">
              <label for="form-host" class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Hôte ou IP
              </label>
              <input
                id="form-host"
                type="text"
                bind:value={formHost}
                required
                placeholder="127.0.0.1"
                class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none"
              />
            </div>
            <div>
              <label for="form-port" class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Port
              </label>
              <input
                id="form-port"
                type="number"
                bind:value={formPort}
                required
                class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none font-mono"
              />
            </div>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label for="form-username" class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Nom d'utilisateur
              </label>
              <input
                id="form-username"
                type="text"
                bind:value={formUsername}
                placeholder="postgres"
                class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none"
              />
            </div>
            <div>
              <label for="form-password" class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                {isEditing ? 'Mot de passe (inchangé si vide)' : 'Mot de passe'}
              </label>
              <input
                id="form-password"
                type="password"
                bind:value={formPassword}
                placeholder="••••••••"
                class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none"
              />
            </div>
          </div>

          <div class="mt-6 pt-4 border-t border-slate-800 flex items-center justify-end gap-3">
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
              <span>{isEditing ? 'Enregistrer les modifications' : 'Ajouter le serveur'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  {/if}

  <!-- Discovery & Selection Modal -->
  {#if showDiscoveryModal}
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
      <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl flex flex-col max-h-[85vh]">
        <!-- Modal Header -->
        <div class="flex items-center justify-between pb-4 border-b border-slate-800">
          <div>
            <h3 class="text-lg font-bold text-white flex items-center gap-2">
              <span>🔍</span> Découverte dynamique des bases
            </h3>
            <p class="text-xs text-slate-400 mt-0.5">
              Serveur : <span class="font-bold text-white">{discoveryTargetServer?.name}</span> ({discoveryTargetServer?.host}:{discoveryTargetServer?.port})
            </p>
          </div>
          <button onclick={() => (showDiscoveryModal = false)} class="text-slate-400 hover:text-white p-1 rounded-lg">
            ✕
          </button>
        </div>

        <!-- Modal Body -->
        <div class="py-4 flex-1 overflow-y-auto space-y-3">
          {#if discovering}
            <div class="py-16 flex flex-col items-center justify-center gap-3 text-slate-400">
              <div class="w-8 h-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin"></div>
              <p class="text-sm font-medium">Interrogation du serveur en cours...</p>
              <p class="text-xs text-slate-500">
                {discoveryTargetServer?.server_type === 'postgresql'
                  ? "Exécution de SELECT datname FROM pg_database WHERE datistemplate = false AND datname != 'postgres'"
                  : 'Requête HTTP GET /repositories'}
              </p>
            </div>
          {:else if discoveredDatabases.length === 0}
            <div class="p-8 text-center text-slate-400">
              <span class="text-3xl block mb-2">🤷</span>
              <p class="text-sm">Aucune base de données ou dépôt trouvé sur cette instance.</p>
            </div>
          {:else}
            <div class="flex items-center justify-between px-1 mb-2 text-xs text-slate-400">
              <span>Bases / Répertoires détectés ({discoveredDatabases.length})</span>
              <span>Cocher pour planifier</span>
            </div>

            <div class="space-y-2">
              {#each discoveredDatabases as db}
                <div
                  onclick={() => !db.already_monitored && toggleDbSelection(db.name)}
                  class="flex items-center justify-between p-3.5 rounded-xl border transition {
                    db.already_monitored
                      ? 'bg-slate-950/40 border-slate-800/60 opacity-60 cursor-not-allowed'
                      : selectedDbNames.includes(db.name)
                        ? 'bg-indigo-500/10 border-indigo-500/80 cursor-pointer'
                        : 'bg-slate-950 border-slate-800 hover:border-slate-700 cursor-pointer'
                  }"
                >
                  <div class="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={selectedDbNames.includes(db.name)}
                      disabled={db.already_monitored}
                      class="w-4 h-4 rounded text-indigo-600 bg-slate-900 border-slate-700 focus:ring-0"
                    />
                    <div>
                      <div class="flex items-center gap-2">
                        <span class="font-bold text-sm text-white font-mono">{db.name}</span>
                        {#if db.already_monitored}
                          <span class="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-medium">
                            Déjà planifié
                          </span>
                        {/if}
                      </div>
                      {#if db.title && db.title !== db.name}
                        <p class="text-xs text-slate-400 mt-0.5">{db.title}</p>
                      {/if}
                    </div>
                  </div>

                  {#if db.size_formatted}
                    <span class="text-xs font-mono text-slate-400 px-2 py-1 rounded bg-slate-900 border border-slate-800">
                      {db.size_formatted}
                    </span>
                  {/if}
                </div>
              {/each}
            </div>
          {/if}
        </div>

        <!-- Modal Footer -->
        <div class="pt-4 border-t border-slate-800 flex items-center justify-between">
          <div class="text-xs text-slate-400">
            {selectedDbNames.length} base{selectedDbNames.length > 1 ? 's' : ''} sélectionnée{selectedDbNames.length > 1 ? 's' : ''}
          </div>

          <div class="flex items-center gap-2">
            <button
              type="button"
              onclick={() => (showDiscoveryModal = false)}
              class="px-4 py-2 rounded-xl text-sm font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
            >
              Fermer
            </button>
            <button
              type="button"
              disabled={selectedDbNames.length === 0 || creatingBatchJobs}
              onclick={handleCreateJobsFromDiscovery}
              class="px-4 py-2 rounded-xl text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white transition flex items-center gap-2"
            >
              {#if creatingBatchJobs}
                <div class="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin"></div>
              {/if}
              <span>Créer les sauvegardes</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>
