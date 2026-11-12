"""fantm API on Modal.

Generation is an in-process asyncio task. Polling the book every 2.5s keeps
the container warm for the length of a run; scaledown_window covers a pause.

    modal secret create fantm-env \
      DATABASE_URL='postgresql://...' \
      JWT_SECRET='(32+ random chars)' \
      GROQ_API_KEY='gsk_...' \
      CORS_ORIGINS='https://fantm.ink,https://YOUR-FANTM.vercel.app'

    modal deploy backend/modal_app.py

URL will be https://jeremy-f-wall--fantm-web.us-east.modal.run
Set that as REACT_APP_BACKEND_URL on the Vercel frontend, then redeploy.
Stripe keys are optional — without them, books still generate; Store checkout
stays off.
"""

import modal

app = modal.App("fantm")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libpq5")
    .pip_install_from_requirements("backend/requirements.prod.txt")
    .add_local_dir("backend", "/root/backend")
)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("fantm-env")],
    timeout=3600,
    scaledown_window=600,
)
@modal.asgi_app()
def web():
    import sys

    sys.path.insert(0, "/root/backend")
    from server import app as fastapi_app

    return fastapi_app
