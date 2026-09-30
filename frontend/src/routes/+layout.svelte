<script>
  import '../app.css';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { apiRequest } from '$lib/api';
  import { currentUser, toastMessage, hideToast, showToast } from '$lib/stores';

  let currentPath = $derived($page.url.pathname);
  let isLoginPage = $derived(currentPath.includes('/login'));

  async function checkAuth() {
    if (isLoginPage) return;
    try {
      const user = await apiRequest('/auth/me');
      currentUser.set(user);
    } catch {
      currentUser.set(null);
      goto('/login');
    }
  }

  async function handleLogout() {
    try {
      await apiRequest('/auth/logout', { method: 'POST' });
    } catch (e) {
      console.error(e);
    }
    currentUser.set(null);
    showToast('Vous avez été déconnecté avec succès', 'info');
    goto('/login');
  }

  onMount(() => {
    checkAuth();
  });
</script>

<div class="min-h-screen bg-slate-950 text-slate-100 flex flex-col md:flex-row antialiased font-sans">
  <!-- Toast Notification Overlay -->
  {#if $toastMessage}
    <div class="fixed top-5 right-5 z-50 max-w-md w-full transition-all duration-300">
      <div class="flex items-center gap-3 p-4 rounded-xl shadow-2xl border backdrop-blur-md {
        $toastMessage.type === 'error' ? 'bg-rose-950/90 border-rose-700/80 text-rose-200' :
        $toastMessage.type === 'success' ? 'bg-emerald-950/90 border-emerald-700/80 text-emerald-200' :
        'bg-slate-900/90 border-slate-700 text-slate-200'
      }">
        <div class="text-xl">
          {#if $toastMessage.type === 'error'}⚠️{/if}
          {#if $toastMessage.type === 'success'}✅{/if}
          {#if $toastMessage.type === 'info'}ℹ️{/if}
        </div>
        <div class="flex-1 text-sm font-medium leading-relaxed">
          {$toastMessage.message}
        </div>
        <button
          onclick={hideToast}
          aria-label="Fermer l'alerte"
          class="text-xs px-2 py-1 rounded hover:bg-white/10 transition"
        >
          ✕
        </button>
      </div>
    </div>
  {/if}

  {#if !isLoginPage}
    <!-- Sidebar Navigation -->
    <aside class="w-full md:w-64 bg-slate-900 border-b md:border-b-0 md:border-r border-slate-800 flex flex-col shrink-0">
      <!-- Brand Logo -->
      <div class="p-6 flex items-center justify-between border-b border-slate-800">
        <a href="/dashboard" class="flex items-center gap-3 group">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-400 flex items-center justify-center text-xl shadow-lg shadow-indigo-500/20 group-hover:scale-105 transition">
            🛡️
          </div>
          <div>
            <h1 class="font-bold text-lg text-white tracking-tight flex items-center gap-1.5">
              Cronstash
              <span class="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">v1.0</span>
            </h1>
            <p class="text-xs text-slate-400 font-medium">Debian 13 Backup Engine</p>
          </div>
        </a>
      </div>

      <!-- Navigation Links -->
      <nav class="p-4 space-y-1.5 flex-1">
        <a
          href="/dashboard"
          class="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition {
            currentPath === '/dashboard' || currentPath === '/'
              ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
              : 'text-slate-300 hover:bg-slate-800/80 hover:text-white'
          }"
        >
          <span class="text-lg">📊</span>
          <span>Tableau de bord</span>
        </a>

        <a
          href="/servers"
          class="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition {
            currentPath.startsWith('/servers')
              ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
              : 'text-slate-300 hover:bg-slate-800/80 hover:text-white'
          }"
        >
          <span class="text-lg">🖥️</span>
          <span>Serveurs & Découverte</span>
        </a>

        <a
          href="/jobs"
          class="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition {
            currentPath.startsWith('/jobs')
              ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
              : 'text-slate-300 hover:bg-slate-800/80 hover:text-white'
          }"
        >
          <span class="text-lg">⏱️</span>
          <span>Tâches planifiées</span>
        </a>

        <a
          href="/backups"
          class="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition {
            currentPath.startsWith('/backups')
              ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
              : 'text-slate-300 hover:bg-slate-800/80 hover:text-white'
          }"
        >
          <span class="text-lg">📁</span>
          <span>Explorateur de backups</span>
        </a>

        <a
          href="/notifications"
          class="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition {
            currentPath.startsWith('/notifications')
              ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
              : 'text-slate-300 hover:bg-slate-800/80 hover:text-white'
          }"
        >
          <span class="text-lg">🔔</span>
          <span>Notifications</span>
        </a>
      </nav>

      <!-- User Profile & Logout -->
      <div class="p-4 border-t border-slate-800">
        <div class="flex items-center justify-between p-2 rounded-lg bg-slate-800/50 border border-slate-700/50">
          <div class="flex items-center gap-2.5 overflow-hidden">
            <div class="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-sm font-bold text-indigo-400">
              👤
            </div>
            <div class="overflow-hidden">
              <p class="text-xs font-semibold text-slate-200 truncate">{$currentUser?.username || 'Admin'}</p>
              <p class="text-[10px] text-emerald-400 flex items-center gap-1 font-medium">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> Connecté
              </p>
            </div>
          </div>
          <button
            onclick={handleLogout}
            title="Se déconnecter"
            class="p-2 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-md transition text-sm"
          >
            🚪
          </button>
        </div>
      </div>
    </aside>
  {/if}

  <!-- Main Content Area -->
  <main class="flex-1 overflow-y-auto">
    <slot />
  </main>
</div>
