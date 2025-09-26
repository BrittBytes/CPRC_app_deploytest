# cprc_app/main.py
from dash import Dash
from app.components import build_app_layout
from app.callbacks import register_callbacks

APP_TITLE = "CPRC Report App"

def create_app() -> Dash:
    app = Dash(__name__, title=APP_TITLE, suppress_callback_exceptions=True)
    app.layout = build_app_layout()
    register_callbacks(app)
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
