<script>
  import { goto } from '$app/navigation';
  import { apiRequest } from '$lib/api';
  import { currentUser, showToast } from '$lib/stores';

  let username = $state('admin');
  let password = $state('');
  let loading = $state(false);
  let errorMessage = $state('');

  async function handleLogin(e) {
    e.preventDefault();
    if (!username || !password) {
      errorMessage = 'Veuillez saisir votre nom d\'utilisateur et votre mot de passe.';
      return;
    }

    loading = true;
    errorMessage = '';

    try {
      const data = await apiRequest('/auth/login', {
        method: 'POST',
        body: { username, password },
      });

      currentUser.set(data.user);
      showToast(`Bienvenue, ${data.user.username} !`, 'success');
      goto('/dashboard');
    } catch (err) {
      errorMessage = err.message || 'Identifiants incorrects';
    } finally {
      loading = false;
    }
  }
</script>

<div class="min-h-screen flex items-center justify-center p-4 bg-slate-950 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(120,119,198,0.15),rgba(255,255,255,0))]">
  <div class="max-w-md w-full bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl relative overflow-hidden">
    <!-- Top subtle glow bar -->
    <div class="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500"></div>

    <div class="text-center mb-8">
      <div class="w-16 h-16 rounded-2xl bg-gradient-to-tr from-indigo-600 to-indigo-400 flex items-center justify-center text-3xl mx-auto shadow-xl shadow-indigo-500/20 mb-4">
        🛡️
      </div>
      <h1 class="text-2xl font-bold tracking-tight text-white">Cronstash</h1>
      <p class="text-sm text-slate-400 mt-1">Gestionnaire de Sauvegardes Automatiques</p>
      <div class="inline-flex items-center gap-1.5 mt-2 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
        <span>PostgreSQL 18</span>
        <span>•</span>
        <span>RDF4J</span>
        <span>•</span>
        <span>Debian 13</span>
      </div>
    </div>

    {#if errorMessage}
      <div class="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm flex items-start gap-3">
        <span class="text-base shrink-0">⚠️</span>
        <div class="font-medium leading-relaxed">{errorMessage}</div>
      </div>
    {/if}

    <form onsubmit={handleLogin} class="space-y-5">
      <div>
        <label for="username" class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
          Identifiant Administrateur
        </label>
        <div class="relative">
          <input
            id="username"
            type="text"
            bind:value={username}
            required
            autocomplete="username"
            class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 outline-none transition"
            placeholder="admin"
          />
        </div>
      </div>

      <div>
        <label for="password" class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
          Mot de Passe
        </label>
        <div class="relative">
          <input
            id="password"
            type="password"
            bind:value={password}
            required
            autocomplete="current-password"
            class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 outline-none transition"
            placeholder="••••••••••••"
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={loading}
        class="w-full py-3.5 px-4 rounded-xl font-semibold text-sm text-white bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-indigo-600/20 transition flex items-center justify-center gap-2"
      >
        {#if loading}
          <div class="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin"></div>
          <span>Connexion sécurisée...</span>
        {:else}
          <span>Se connecter</span>
          <span>→</span>
        {/if}
      </button>
    </form>

    <div class="mt-8 text-center border-t border-slate-800/80 pt-6">
      <p class="text-xs text-slate-500">
        Authentification Argon2id & JWT HTTPOnly SameSite
      </p>
    </div>
  </div>
</div>
