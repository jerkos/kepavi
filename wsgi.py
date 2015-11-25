from kepavi.app import create_app
from kepavi.configs.default import DefaultConfig as Config


flaskbb = create_app(Config)


if __name__ == "__main__":
    flaskbb.run()
