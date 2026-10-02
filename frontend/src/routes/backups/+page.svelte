<script>
  import { onMount } from 'svelte';
  import { apiRequest, formatDate, formatBytes } from '$lib/api';
  import { showToast } from '$lib/stores';

  let files = $state([]);
  let servers = $state([]);
  let loading = $state(true);
  let filterType = $state('all'); // 'all', 'pgsql', 'rdf4j'
  let searchQuery = $state('');

  // Instant Backup Modal
  let showInstantModal = $state(false);
  let instantServerId = $state('');
  let instantDbName = $state('');
  let runningInstant = $state(false);

  async function loadBackups() {
    try {
      const [filesData, serversData] = await Promise.all([
        apiRequest('/backups'),
        apiRequest('/servers'),
      ]);
      files = filesData;
      servers = serversData;
      if (servers.length > 0 && !instantServerId) {
        instantServerId = servers[0].id;
      }
    } catch (err) {
      showToast('Erreur chargement des sauvegardes: ' + err.message, 'error');
    } finally {
      loading = false;
    }
  }

  let filteredFiles = $derived(
    files.filter((f) => {
      const matchesType = filterType === 'all' || f.server_type === filterType;
      const q = searchQuery.toLowerCase().trim();
      const matchesQuery =
        !q ||
        f.file_name.toLowerCase().includes(q) ||
        f.server_name.toLowerCase().includes(q) ||
        f.database_name.toLowerCase().includes(q);
      return matchesType && matchesQuery;
    })
  );

  async function handleDeleteFile(file) {
    if (!confirm(`Supprimer définitivement l'archive '${file.file_name}' (${file.size_formatted}) du disque ?`)) {
      return;
    }
    try {
      await apiRequest(`/backups/${encodeURIComponent(file.relative_path)}`, { method: 'DELETE' });
      showToast(`Archive '${file.file_name}' supprimée`, 'info');
      await loadBackups();
    } catch (err) {
      showToast('Erreur suppression: ' + err.message, 'error');
    }
  }

  function handleDownload(file) {
    // Direct link to download endpoint
    window.location.href = `/api/backups/download/${encodeURIComponent(file.relative_path)}`;
  }

  async function handleTriggerInstant(e) {
    e.preventDefault();
    if (!instantServerId || !instantDbName) {
      showToast('Veuillez remplir tous les champs', 'error');
      return;
    }

    runningInstant = true;
    showToast(`Déclenchement de la sauvegarde manuelle pour ${instantDbName}...`, 'info');

    try {
      const res = await apiRequest('/backups/instant', {
        method: 'POST',
        body: {
          server_id: Number(instantServerId),
          database_name: instantDbName.trim(),
        }
      });

      if (res.status === 'success') {
        showToast(`Sauvegarde de ${instantDbName} terminée avec succès !`, 'success');
      } else {
        showToast(`Échec de sauvegarde: ${res.error_message}`, 'error', 6000);
      }
      showInstantModal = false;
      instantDbName = '';
      await loadBackups();
    } catch (err) {
      showToast('Erreur: ' + err.message, 'error');
    } finally {
      runningInstant = false;
    }
  }

  onMount(() => {
    loadBackups();
  });
</script>

<div class="p-6 md:p-10 max-w-7xl mx-auto space-y-8">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <h1 class="text-2xl md:text-3xl font-bold tracking-tight text-white flex items-center gap-3">
        Explorateur de Sauvegardes
      </h1>
      <p class="text-sm text-slate-400 mt-1">
        Archives physiques stockées dans <span class="font-mono text-indigo-400">/backup/cronstash/</span> (pgsql & rdf4j)
      </p>
    </div>

    <div class="flex items-center gap-3">
      <button
        onclick={() => (showInstantModal = true)}
        class="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white shadow-md shadow-emerald-600/20 transition"
      >
        <span>⚡</span>
        <span>Sauvegarde instantanée</span>
      </button>
    </div>
  </div>

  <!-- Filters & Search Bar -->
  <div class="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-col md:flex-row gap-4 items-center justify-between">
    <!-- Type Filter Tabs -->
    <div class="flex items-center gap-1.5 bg-slate-950 p-1 rounded-xl border border-slate-800 w-full md:w-auto">
      <button
        onclick={() => (filterType = 'all')}
        class="px-3.5 py-1.5 rounded-lg text-xs font-semibold transition {
          filterType === 'all' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'
        }"
      >
        Tous ({files.length})
      </button>

      <button
        onclick={() => (filterType = 'pgsql')}
        class="px-3.5 py-1.5 rounded-lg text-xs font-semibold transition {
          filterType === 'pgsql' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'
        }"
      >
        🐘 PostgreSQL ({files.filter(f => f.server_type === 'pgsql').length})
      </button>

      <button
        onclick={() => (filterType = 'rdf4j')}
        class="px-3.5 py-1.5 rounded-lg text-xs font-semibold transition {
          filterType === 'rdf4j' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'
        }"
      >
        🌐 RDF4J ({files.filter(f => f.server_type === 'rdf4j').length})
      </button>
    </div>

    <!-- Search Input -->
    <div class="w-full md:w-72 relative">
      <input
        type="text"
        bind:value={searchQuery}
        placeholder="Rechercher une archive..."
        class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl pl-9 pr-4 py-2 text-xs text-white placeholder-slate-500 outline-none"
      />
      <span class="absolute left-3 top-2.5 text-xs text-slate-500">🔍</span>
    </div>
  </div>

  {#if loading}
    <div class="py-20 flex justify-center text-slate-400">
      <div class="w-8 h-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin"></div>
    </div>
  {:else if filteredFiles.length === 0}
    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center shadow-sm">
      <span class="text-4xl block mb-3">📁</span>
      <h3 class="text-lg font-semibold text-white">Aucun fichier de sauvegarde trouvé</h3>
      <p class="text-sm text-slate-400 max-w-md mx-auto mt-1 mb-6">
        Les archives générées par pg_dump et le streaming RDF4J apparaîtront dans cette liste.
      </p>
      <button
        onclick={() => (showInstantModal = true)}
        class="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition"
      >
        <span>⚡ Lancer une sauvegarde instantanée</span>
      </button>
    </div>
  {:else}
    <!-- Backups Table -->
    <div class="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-sm">
      <div class="overflow-x-auto">
        <table class="w-full text-left text-sm text-slate-300">
          <thead class="bg-slate-950/70 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800">
            <tr>
              <th class="py-3 px-4">Moteur</th>
              <th class="py-3 px-4">Fichier Archive</th>
              <th class="py-3 px-4">Serveur & Base</th>
              <th class="py-3 px-4">Taille</th>
              <th class="py-3 px-4">Date de Création</th>
              <th class="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60">
            {#each filteredFiles as file}
              <tr class="hover:bg-slate-800/40 transition">
                <td class="py-3.5 px-4">
                  <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-medium {
                    file.server_type === 'pgsql' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                  }">
                    {file.server_type === 'pgsql' ? '🐘 PGSQL' : '🌐 RDF4J'}
                  </span>
                </td>

                <td class="py-3.5 px-4 font-mono text-xs text-white">
                  <div class="font-semibold text-slate-100">{file.file_name}</div>
                  <div class="text-[11px] text-slate-500 truncate max-w-xs">{file.relative_path}</div>
                </td>

                <td class="py-3.5 px-4">
                  <div class="flex items-center gap-1.5">
                    <span class="font-medium text-slate-200">{file.server_name}</span>
                    <span class="text-slate-500">/</span>
                    <span class="text-slate-300 font-mono text-xs">{file.database_name}</span>
                  </div>
                </td>

                <td class="py-3.5 px-4 font-mono text-xs text-slate-200">
                  {file.size_formatted}
                </td>

                <td class="py-3.5 px-4 text-xs text-slate-400">
                  {formatDate(file.modified_at)}
                </td>

                <td class="py-3.5 px-4 text-right space-x-1">
                  <button
                    onclick={() => handleDownload(file)}
                    title="Télécharger l'archive"
                    class="p-2 text-indigo-400 hover:text-white hover:bg-indigo-600/20 rounded-lg transition"
                  >
                    📥
                  </button>

                  <button
                    onclick={() => handleDeleteFile(file)}
                    title="Supprimer du stockage"
                    class="p-2 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition"
                  >
                    🗑️
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}

  <!-- Instant Backup Modal -->
  {#if showInstantModal}
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
      <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl">
        <div class="flex items-center justify-between pb-4 border-b border-slate-800">
          <h3 class="text-lg font-bold text-white flex items-center gap-2">
            <span>⚡</span> Sauvegarde Instantanée à la Demande
          </h3>
          <button onclick={() => (showInstantModal = false)} class="text-slate-400 hover:text-white p-1 rounded-lg">
            ✕
          </button>
        </div>

        <form onsubmit={handleTriggerInstant} class="mt-5 space-y-4">
          <div>
            <label for="instant-server-select" class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Serveur Cible
            </label>
            <select
              id="instant-server-select"
              bind:value={instantServerId}
              required
              class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none"
            >
              {#each servers as s}
                <option value={s.id}>{s.name} ({s.server_type})</option>
              {/each}
            </select>
          </div>

          <div>
            <label for="instant-db-input" class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Nom de la Base ou Repository
            </label>
            <input
              id="instant-db-input"
              type="text"
              bind:value={instantDbName}
              required
              placeholder="ex: ma_base_de_donnees"
              class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none font-mono"
            />
          </div>

          <div class="pt-4 border-t border-slate-800 flex items-center justify-end gap-3">
            <button
              type="button"
              onclick={() => (showInstantModal = false)}
              class="px-4 py-2.5 rounded-xl text-sm font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
            >
              Annuler
            </button>
            <button
              type="submit"
              disabled={runningInstant}
              class="px-5 py-2.5 rounded-xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 disabled:opacity-50 text-white transition flex items-center gap-2"
            >
              {#if runningInstant}
                <div class="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin"></div>
                <span>Dump en cours...</span>
              {:else}
                <span>Lancer la sauvegarde</span>
              {/if}
            </button>
          </div>
        </form>
      </div>
    </div>
  {/if}
</div>
