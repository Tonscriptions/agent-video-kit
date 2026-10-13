---
name: video-cut-remotion-saas
description: Build an app with Remotion
metadata:
  upstream_fields:
    version: 4.0.534
  video_cut_source:
    repository: remotion-dev/skills
    commit: 32b241b97f4e0e4ab61fe9a41b05e6e64503f8c5
    path: skills/remotion-saas
    original_name: remotion-saas
---

Read [local installation rules](references/local-installation.md) before running the upstream workflow.

One can build apps with Remotion.  
It is possible to have a simple form and hook it up to a render, or have a complex video editor.

## Choosing a template or a framework

We have several templates for SaaS which can be cloned or used as a reference.
See [Choosing a framework](framework.md) for help choosing a template or framework.

## The `<Player>`

This component allows embedding a Remotion preview in a React app. See [Player](player.md) for more information about the Player.

## Rendering

There are client-side and server-side rendering options available. See [Rendering](rendering.md) for advice on how to choose, and about the Lambda, Vercel, Node.js and Cloudflare options.

## With Vue

See https://www.remotion.dev/docs/vue.md for how to use Remotion with Vue.

## Angular

See https://www.remotion.dev/docs/angular.md for how to use Remotion with Angular.

## Svelte

See https://www.remotion.dev/docs/svelte.md for how to use Remotion with Svelte.
