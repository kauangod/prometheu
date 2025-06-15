class State:
    def __init__(self):
        self.state_stack = list()
        self.possible_states = ["PIN_CHK", "MNEM_GEN", "MNEM_REG", "PIN_REG", "MAIN_MENU"]

    @classmethod
    def add_state(self, state):
        if state in self.possible_states:
            self.state_stack.append(state)

    @classmethod
    def get_current_state(self):
        return self.state_stack[-1]

    @classmethod
    def pop_state(self) -> None:
        self.state_stack.pop()