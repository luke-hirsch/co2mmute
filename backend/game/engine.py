class Dijkstra:
    def __init__(self, startNode, endNode) -> None:
        self.startNode = startNode
        self.endNode = endNode

    def velocity(self, x, t):
        return x / t

    class Walking:
        def cost_x_t(self, x, t):
            pass

        def time_x(self, v, x):
            return

    class Bike:
        pass

    class Car:
        pass

    class PublicTransport:
        pass

    def way_time(self):
        pass

    def way_emissions(self, transportation):
        if transportation == "car":
            return 120.0
        elif transportation == "public":
            return 60.0
        else:
            return 0.0

    def way_cost(self):
        pass

    def car_emmissions_x_t(self):
        pass
