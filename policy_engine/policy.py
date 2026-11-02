class PolicyEngine:
    def __init__(self):
        self.policies = {}
    def add_policy(self, name, func):
        self.policies[name] = func
    def evaluate(self, name, *args, **kwargs):
        return self.policies[name](*args, **kwargs)
