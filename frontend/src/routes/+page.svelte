<script lang="ts">
  import { onMount } from 'svelte';
  import '../app.css';

  let health: Record<string, unknown> | null = null;

  onMount(async () => {
    const res = await fetch('/api/health');
    health = await res.json();
  });
</script>

<main>
  <h1>Blitzerr</h1>
  <p>NFL game media collection manager</p>
  {#if health}
    <pre>{JSON.stringify(health, null, 2)}</pre>
  {:else}
    <p>Connecting to backend…</p>
  {/if}
</main>
