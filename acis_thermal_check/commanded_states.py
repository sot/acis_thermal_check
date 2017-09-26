
class CommandedStates(object):
    def __init__(self, states):
        self.states = states

    def __getitem__(self, item):
        return self.states[item]

class StatesFromDatabase(CommandedStates):
    def __init__(self, tstart, tstop):
        states = {}
        super(StatesFromDatabase, self).__init__(states)

class StatesFromBackstop(CommandedStates):
    def __init__(self):
        pass