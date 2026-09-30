<script>
  import { onMount } from 'svelte';
  import { apiRequest, formatDate, formatBytes } from '$lib/api';
  import { showToast } from '$lib/stores';

  let stats = $state(null);
  let loading = $state(true);
  let refreshing = $state(false);
  let selectedError = $state(null);

  async function loadStats() {
    try {
      stats = await apiRequest('/dashboard/stats');
    } catch (err) {
      showToast('Erreur lors du chargement des statistiques: ' + err.message, 'error');
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  function handleRefresh() {
    refreshing = true;
    loadStats();
  }

  onMount(() => {
    loadStats();
  });
</script>

<div class="p-6 md:p-10 max-w-7xl mx-auto space-y-8">
  <!-- Header Title -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <h1 class="text-2xl md:text-3xl font-bold tracking-tight text-white flex items-center gap-3">
        Tableau de bord
        <span class="text-xs px-2.5 py-1 rounded-full bg-slate-800 text-slate-400 border border-slate-700 font-normal">
          Debian 13 (Trixie)
        </span>
      </h1>
      <p class="text-sm text-slate-400 mt-1">Supervision des sauvegardes automatiques PostgreSQL 18 & RDF4J</p>
    </div>

    <div class="flex items-center gap-3">
      <button
        onclick={handleRefresh}
        disabled={refreshing}
        class="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-sm font-medium bg-slate-800 hover:bg-slate-700 active:bg-slate-800 text-slate-200 border border-slate-700 transition"
      >
        <span class={refreshing ? 'animate-spin inline-block' : ''}>🔄</span>
        <span>Rafraîchir</span>
      </button>

      <a
        href="/jobs"
        class="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20 transition"
      >
        <span>➕</span>
        <span>Nouvelle tâche</span>
      </a>
    </div>
  </div>

  {#if loading}
    <div class="py-20 flex flex-col items-center justify-center gap-4 text-slate-400">
      <div class="w-8 h-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin"></div>
      <p class="text-sm">Chargement des données du système...</p>
    </div>
  {:else if stats}
    <!-- Top KPI Grid -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
      <!-- Disk Usage Widget -->
      <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm relative overflow-hidden flex flex-col justify-between">
        <div class="flex items-center justify-between">
          <span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Espace Sauvegardes</span>
          <span class="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 text-lg">💾</span>
        </div>
        <div class="mt-4">
          <div class="flex items-baseline justify-between">
            <span class="text-2xl font-bold text-white">{stats.disk.used_formatted}</span>
            <span class="text-xs text-slate-400">sur {stats.disk.total_formatted}</span>
          </div>
          <!-- Progress bar -->
          <div class="w-full bg-slate-800 h-2 rounded-full mt-3 overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-500 {
                stats.disk.used_percent > 85 ? 'bg-rose-500' :
                stats.disk.used_percent > 70 ? 'bg-amber-500' : 'bg-indigo-500'
              }"
              style="width: {stats.disk.used_percent}%"
            ></div>
          </div>
          <div class="flex items-center justify-between mt-2 text-xs text-slate-400">
            <span>{stats.disk.used_percent}% occupé</span>
            <span class="text-emerald-400 font-medium">{stats.disk.free_formatted} libres</span>
          </div>
        </div>
      </div>

      <!-- 24h Success Rate Widget -->
      <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm flex flex-col justify-between">
        <div class="flex items-center justify-between">
          <span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Taux de Réussite (24h)</span>
          <span class="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 text-lg">🎯</span>
        </div>
        <div class="mt-4">
          <div class="flex items-baseline justify-between">
            <span class="text-2xl font-bold {stats.stats_24h.success_rate >= 90 ? 'text-emerald-400' : 'text-amber-400'}">
              {stats.stats_24h.success_rate}%
            </span>
            <span class="text-xs text-slate-400">
              {stats.stats_24h.total_runs} exécution{stats.stats_24h.total_runs > 1 ? 's' : ''}
            </span>
          </div>
          <div class="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-slate-800 text-xs">
            <div class="flex items-center gap-1.5 text-emerald-400">
              <span>✓</span>
              <span>{stats.stats_24h.success_runs} succès</span>
            </div>
            <div class="flex items-center gap-1.5 text-rose-400">
              <span>✕</span>
              <span>{stats.stats_24h.failed_runs} échec{stats.stats_24h.failed_runs > 1 ? 's' : ''}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Total Servers Widget -->
      <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm flex flex-col justify-between">
        <div class="flex items-center justify-between">
          <span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Serveurs Connectés</span>
          <span class="p-2 rounded-lg bg-sky-500/10 text-sky-400 text-lg">🖥️</span>
        </div>
        <div class="mt-4">
          <span class="text-2xl font-bold text-white">{stats.total_servers}</span>
          <p class="text-xs text-slate-400 mt-2">PostgreSQL & clusters RDF4J</p>
          <div class="mt-3 pt-3 border-t border-slate-800">
            <a href="/servers" class="text-xs text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1">
              Gérer les serveurs →
            </a>
          </div>
        </div>
      </div>

      <!-- Active Jobs Widget -->
      <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm flex flex-col justify-between">
        <div class="flex items-center justify-between">
          <span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Tâches Planifiées</span>
          <span class="p-2 rounded-lg bg-purple-500/10 text-purple-400 text-lg">⏱️</span>
        </div>
        <div class="mt-4">
          <div class="flex items-baseline justify-between">
            <span class="text-2xl font-bold text-white">{stats.active_jobs}</span>
            <span class="text-xs text-slate-400">sur {stats.total_jobs} configurées</span>
          </div>
          <p class="text-xs text-slate-400 mt-2">Synchronisées dans /etc/cron.d/cronstash</p>
          <div class="mt-3 pt-3 border-t border-slate-800">
            <a href="/jobs" class="text-xs text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1">
              Voir le planning →
            </a>
          </div>
        </div>
      </div>
    </div>

    <!-- Recent Logs Table -->
    <div class="bg-slate-900 border border-slate-800 rounded-2xl shadow-sm overflow-hidden">
      <div class="p-5 border-b border-slate-800 flex items-center justify-between">
        <div>
          <h2 class="text-base font-semibold text-white">Dernières Sauvegardes</h2>
          <p class="text-xs text-slate-400 mt-0.5">Historique d'exécution des tâches en temps réel</p>
        </div>
        <a href="/backups" class="text-xs font-medium text-indigo-400 hover:text-indigo-300">
          Explorateur d'archives →
        </a>
      </div>

      {#if stats.recent_logs.length === 0}
        <div class="p-12 text-center text-slate-500">
          <span class="text-3xl block mb-2">📭</span>
          <p class="text-sm font-medium">Aucun journal de sauvegarde disponible.</p>
          <p class="text-xs text-slate-600 mt-1">Les sauvegardes exécutées apparaîtront automatiquement ici.</p>
        </div>
      {:else}
        <div class="overflow-x-auto">
          <table class="w-full text-left text-sm text-slate-300">
            <thead class="bg-slate-950/60 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800">
              <tr>
                <th class="py-3 px-4">Statut</th>
                <th class="py-3 px-4">Tâche</th>
                <th class="py-3 px-4">Serveur & Base</th>
                <th class="py-3 px-4">Taille</th>
                <th class="py-3 px-4">Durée</th>
                <th class="py-3 px-4">Horodatage</th>
                <th class="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-800/60">
              {#each stats.recent_logs as log}
                <tr class="hover:bg-slate-800/40 transition">
                  <td class="py-3.5 px-4">
                    {#if log.status === 'success'}
                      <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                        Succès
                      </span>
                    {:else if log.status === 'failed'}
                      <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                        <span class="w-1.5 h-1.5 rounded-full bg-rose-400"></span>
                        Échec
                      </span>
                    {:else}
                      <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse">
                        En cours...
                      </span>
                    {/if}
                  </td>

                  <td class="py-3.5 px-4 font-medium text-white">
                    {log.job_name}
                  </td>

                  <td class="py-3.5 px-4">
                    <div class="flex items-center gap-2">
                      <span class="text-xs px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 uppercase font-mono">
                        {log.server_type}
                      </span>
                      <span class="font-medium text-slate-200">{log.server_name}</span>
                      <span class="text-slate-500">/</span>
                      <span class="text-slate-300 font-mono text-xs">{log.database_name}</span>
                    </div>
                  </td>

                  <td class="py-3.5 px-4 text-slate-300 font-mono text-xs">
                    {formatBytes(log.file_size_bytes)}
                  </td>

                  <td class="py-3.5 px-4 text-slate-400 text-xs">
                    {log.duration_seconds ? `${log.duration_seconds}s` : '-'}
                  </td>

                  <td class="py-3.5 px-4 text-slate-400 text-xs">
                    {formatDate(log.started_at)}
                  </td>

                  <td class="py-3.5 px-4 text-right">
                    {#if log.error_message}
                      <button
                        onclick={() => (selectedError = log.error_message)}
                        class="text-xs text-rose-400 hover:text-rose-300 underline font-medium"
                      >
                        Voir erreur
                      </button>
                    {:else if log.gfs_tier}
                      <span class="text-[11px] px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 font-medium">
                        GFS: {log.gfs_tier}
                      </span>
                    {:else}
                      <span class="text-slate-600 text-xs">-</span>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {/if}

  <!-- Error Detail Modal -->
  {#if selectedError}
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 shadow-2xl">
        <div class="flex items-center justify-between pb-4 border-b border-slate-800">
          <h3 class="text-lg font-bold text-rose-400 flex items-center gap-2">
            <span>⚠️</span> Détail de l'erreur d'exécution
          </h3>
          <button
            onclick={() => (selectedError = null)}
            class="text-slate-400 hover:text-white p-1 rounded-lg"
          >
            ✕
          </button>
        </div>
        <div class="mt-4 p-4 rounded-xl bg-slate-950 border border-slate-800 overflow-x-auto max-h-96">
          <pre class="text-xs font-mono text-rose-300 whitespace-pre-wrap">{selectedError}</pre>
        </div>
        <div class="mt-6 flex justify-end">
          <button
            onclick={() => (selectedError = null)}
            class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-sm font-medium transition"
          >
            Fermer
          </button>
        </div>
      </div>
    </div>
  {/if}
</div>
