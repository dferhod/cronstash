<script>
  import { onMount } from 'svelte';
  import { apiRequest } from '$lib/api';
  import { showToast } from '$lib/stores';

  let config = $state({
    smtp_enabled: false,
    smtp_host: '',
    smtp_port: 587,
    smtp_username: '',
    smtp_password: '',
    smtp_use_tls: true,
    smtp_from: '',
    smtp_to: '',
    discord_enabled: false,
    discord_webhook_url: '',
    notify_on_success: false,
    notify_on_failure: true,
  });

  let loading = $state(true);
  let saving = $state(false);
  let testingSmtp = $state(false);
  let testingDiscord = $state(false);

  async function loadConfig() {
    try {
      config = await apiRequest('/notifications');
    } catch (err) {
      showToast('Erreur chargement notifications: ' + err.message, 'error');
    } finally {
      loading = false;
    }
  }

  async function handleSaveConfig(e) {
    e?.preventDefault();
    saving = true;

    try {
      const updated = await apiRequest('/notifications', {
        method: 'PUT',
        body: config,
      });
      config = updated;
      showToast('Configuration des notifications enregistrée avec succès !', 'success');
    } catch (err) {
      showToast('Erreur enregistrement: ' + err.message, 'error');
    } finally {
      saving = false;
    }
  }

  async function handleTestSmtp() {
    testingSmtp = true;
    showToast('Envoi d\'un e-mail de test SMTP en cours...', 'info');

    try {
      // First save current values
      await apiRequest('/notifications', { method: 'PUT', body: config });
      const res = await apiRequest('/notifications/test-smtp', { method: 'POST' });
      if (res.success) {
        showToast(res.message, 'success');
      } else {
        showToast(res.message, 'error', 6000);
      }
    } catch (err) {
      showToast('Échec du test SMTP: ' + err.message, 'error');
    } finally {
      testingSmtp = false;
    }
  }

  async function handleTestDiscord() {
    if (!config.discord_webhook_url) {
      showToast('Veuillez renseigner l\'URL du webhook Discord', 'error');
      return;
    }

    testingDiscord = true;
    showToast('Envoi d\'un Embed de test Discord...', 'info');

    try {
      await apiRequest('/notifications', { method: 'PUT', body: config });
      const res = await apiRequest('/notifications/test-discord', { method: 'POST' });
      if (res.success) {
        showToast(res.message, 'success');
      } else {
        showToast(res.message, 'error', 6000);
      }
    } catch (err) {
      showToast('Échec du test Discord: ' + err.message, 'error');
    } finally {
      testingDiscord = false;
    }
  }

  onMount(() => {
    loadConfig();
  });
</script>

<div class="p-6 md:p-10 max-w-5xl mx-auto space-y-8">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <h1 class="text-2xl md:text-3xl font-bold tracking-tight text-white flex items-center gap-3">
        Paramètres de Notifications
      </h1>
      <p class="text-sm text-slate-400 mt-1">
        Alertes par courriel HTML (SMTP) et Webhooks Discord enrichis avec embeds détaillés
      </p>
    </div>

    <button
      onclick={handleSaveConfig}
      disabled={saving}
      class="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20 transition"
    >
      {#if saving}
        <div class="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin"></div>
      {:else}
        <span>💾</span>
      {/if}
      <span>Enregistrer les paramètres</span>
    </button>
  </div>

  {#if loading}
    <div class="py-20 flex justify-center text-slate-400">
      <div class="w-8 h-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin"></div>
    </div>
  {:else}
    <div class="grid grid-cols-1 gap-8">
      <!-- General Rules -->
      <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm">
        <h2 class="text-base font-bold text-white mb-1">Règles de Déclenchement</h2>
        <p class="text-xs text-slate-400 mb-4">Choisissez les événements qui doivent déclencher les alertes</p>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label class="flex items-start gap-3 p-4 rounded-xl border cursor-pointer transition {
            config.notify_on_failure ? 'bg-rose-500/10 border-rose-500/50 text-white' : 'bg-slate-950 border-slate-800 text-slate-400'
          }">
            <input type="checkbox" bind:checked={config.notify_on_failure} class="mt-1 w-4 h-4 rounded text-rose-600 focus:ring-0" />
            <div>
              <span class="text-sm font-bold block text-rose-300">Alerter en cas d'Échec (Recommandé)</span>
              <span class="text-xs text-slate-400">Envoie un rapport immédiat avec la trace d'erreur en cas de rejet par pg_dump ou timeout.</span>
            </div>
          </label>

          <label class="flex items-start gap-3 p-4 rounded-xl border cursor-pointer transition {
            config.notify_on_success ? 'bg-emerald-500/10 border-emerald-500/50 text-white' : 'bg-slate-950 border-slate-800 text-slate-400'
          }">
            <input type="checkbox" bind:checked={config.notify_on_success} class="mt-1 w-4 h-4 rounded text-emerald-600 focus:ring-0" />
            <div>
              <span class="text-sm font-bold block text-emerald-300">Alerter en cas de Succès</span>
              <span class="text-xs text-slate-400">Envoie une notification confirmant la taille de l'archive et le tier GFS appliqué.</span>
            </div>
          </label>
        </div>
      </div>

      <!-- Discord Webhook Card -->
      <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-5">
        <div class="flex items-center justify-between border-b border-slate-800 pb-4">
          <div class="flex items-center gap-3">
            <span class="text-2xl p-2 rounded-xl bg-indigo-500/10 text-indigo-400">💬</span>
            <div>
              <h2 class="text-base font-bold text-white">Canal Discord (Webhooks)</h2>
              <p class="text-xs text-slate-400">Embeds riches avec code couleur vert/rouge, durée et taille</p>
            </div>
          </div>

          <label class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none {
            config.discord_enabled ? 'bg-indigo-600' : 'bg-slate-800'
          }">
            <input type="checkbox" bind:checked={config.discord_enabled} class="hidden" />
            <span class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out {
              config.discord_enabled ? 'translate-x-5' : 'translate-x-0'
            }"></span>
          </label>
        </div>

        <div>
          <label for="discord-webhook-url" class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
            URL du Webhook Discord
          </label>
          <input
            id="discord-webhook-url"
            type="url"
            bind:value={config.discord_webhook_url}
            placeholder="https://discord.com/api/webhooks/..."
            class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm font-mono text-white outline-none"
          />
        </div>

        <div class="pt-2 flex justify-end">
          <button
            type="button"
            onclick={handleTestDiscord}
            disabled={testingDiscord || !config.discord_webhook_url}
            class="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-indigo-300 border border-slate-700 transition"
          >
            {#if testingDiscord}
              <div class="w-3.5 h-3.5 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin"></div>
            {:else}
              <span>🧪</span>
            {/if}
            <span>Tester le Webhook Discord</span>
          </button>
        </div>
      </div>

      <!-- SMTP Email Card -->
      <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-5">
        <div class="flex items-center justify-between border-b border-slate-800 pb-4">
          <div class="flex items-center gap-3">
            <span class="text-2xl p-2 rounded-xl bg-blue-500/10 text-blue-400">📧</span>
            <div>
              <h2 class="text-base font-bold text-white">Serveur de Messagerie (SMTP)</h2>
              <p class="text-xs text-slate-400">Courriels au format HTML mis en forme avec récapitulatif système</p>
            </div>
          </div>

          <label class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none {
            config.smtp_enabled ? 'bg-indigo-600' : 'bg-slate-800'
          }">
            <input type="checkbox" bind:checked={config.smtp_enabled} class="hidden" />
            <span class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out {
              config.smtp_enabled ? 'translate-x-5' : 'translate-x-0'
            }"></span>
          </label>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div class="sm:col-span-2">
            <label for="smtp-host-input" class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Hôte SMTP
            </label>
            <input
              id="smtp-host-input"
              type="text"
              bind:value={config.smtp_host}
              placeholder="smtp.example.com"
              class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none"
            />
          </div>

          <div>
            <label for="smtp-port-input" class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Port
            </label>
            <input
              id="smtp-port-input"
              type="number"
              bind:value={config.smtp_port}
              placeholder="587"
              class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none font-mono"
            />
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label for="smtp-username-input" class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Utilisateur SMTP
            </label>
            <input
              id="smtp-username-input"
              type="text"
              bind:value={config.smtp_username}
              placeholder="backups@example.com"
              class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none"
            />
          </div>

          <div>
            <label for="smtp-password-input" class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Mot de passe
            </label>
            <input
              id="smtp-password-input"
              type="password"
              bind:value={config.smtp_password}
              placeholder="••••••••••••"
              class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none"
            />
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label for="smtp-from-input" class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Expéditeur (From)
            </label>
            <input
              id="smtp-from-input"
              type="email"
              bind:value={config.smtp_from}
              placeholder="Cronstash &lt;cronstash@domain.com&gt;"
              class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none"
            />
          </div>

          <div>
            <label for="smtp-to-input" class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Destinataire des alertes (To)
            </label>
            <input
              id="smtp-to-input"
              type="email"
              bind:value={config.smtp_to}
              placeholder="sysadmin@domain.com"
              class="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none"
            />
          </div>
        </div>

        <div class="flex items-center gap-3">
          <input
            type="checkbox"
            id="smtp-tls"
            bind:checked={config.smtp_use_tls}
            class="w-4 h-4 rounded text-indigo-600 focus:ring-0 bg-slate-950 border-slate-800"
          />
          <label for="smtp-tls" class="text-xs text-slate-300 cursor-pointer">
            Activer STARTTLS (Chiffrement sécurisé des échanges)
          </label>
        </div>

        <div class="pt-2 flex justify-end">
          <button
            type="button"
            onclick={handleTestSmtp}
            disabled={testingSmtp || !config.smtp_host}
            class="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-blue-300 border border-slate-700 transition"
          >
            {#if testingSmtp}
              <div class="w-3.5 h-3.5 rounded-full border-2 border-blue-400 border-t-transparent animate-spin"></div>
            {:else}
              <span>🧪</span>
            {/if}
            <span>Tester l'envoi SMTP</span>
          </button>
        </div>
      </div>
    </div>
  {/if}
</div>
