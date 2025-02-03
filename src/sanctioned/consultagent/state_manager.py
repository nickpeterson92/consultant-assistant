# state_manager.py


class StateManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StateManager, cls).__new__(cls)
            cls._instance.state = {}
        return cls._instance

    def get_state(self):
        return self.state

    def update_state(self, update, value=None):
        if isinstance(update, dict) and value is None:
            self.state.update(update)
        elif value is not None:
            self.state[update] = value
        else:
            raise ValueError("Provide either a dict or a key and value pair.")