class MCPAdapter:
    def __init__(self, client):
        self.client = client
    def call(self, tool, *args, **kwargs):
        return self.client.invoke(tool, *args, **kwargs)

class A2AAdapter:
    def __init__(self, channel):
        self.channel = channel
    def send(self, message):
        self.channel.publish(message)
