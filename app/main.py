"""KisanSetu FastAPI app.

Serves three static pages from web/ (no build step):
  GET /                  -> web/landing.html
  GET /demo              -> web/demo.html   (the live demo, its own page)
  GET /fpo               -> web/fpo.html    (FPO dashboard, no login)
  GET /health

APIs:
  /api/farmer/*          -> demo-console send/poll (web_console transport)
  /api/fpo/*             -> upload, staged-review approve/discard, advisory,
                            staff chatbot
  /api/demo/trigger      -> fires an EXTERNAL simulated event only (climate
                            alert, FPO batch upload, agent-activity view).
                            The chat itself is a real live agent, never a
                            scripted playback — see CLAUDE.md.
  /api/alerts            -> current climate-alert feed
  /webhook/whatsapp      -> real Meta WhatsApp Cloud API webhook

The climate-watch scheduler loop starts on @app.on_event("startup").
"""
