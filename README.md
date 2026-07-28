---
title: AI Career Co-Pilot
emoji: 🚀
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# AI Career Co-Pilot

An on-device career assistant: resume review, ATS scoring, mock interviews,
skill roadmaps and recruiter outreach drafts.

## About this hosted demo

The project is built **local-first**: on a laptop it runs entirely offline
against [Ollama](https://ollama.com), with no API keys and no data leaving the
machine.

This public demo exists so it can be tried without installing anything. Free CPU
hosting cannot run a 3B model at interactive speed — a single answer takes one
to three minutes — so the hosted build keeps the same API contract but forwards
generation to a hosted inference provider. Embeddings still run locally inside
the container.

The application code is identical in both modes. The swap happens behind
`OLLAMA_URL`, which is why nothing in `app/` changes between them.
