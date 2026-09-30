<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  onMount(() => {
    goto('/dashboard');
  });
</script>

<div class="h-full flex items-center justify-center p-8">
  <div class="animate-pulse flex items-center gap-3 text-slate-400 text-sm">
    <div class="w-4 h-4 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin"></div>
    <span>Chargement de Cronstash...</span>
  </div>
</div>
