from maps.models import Node
from models import (
    BikeMobility,
    CarMobility,
    BusMobility,
    TrainMobility,
    WalkingMobility,GameRound
)


class Dijkstra:
    def __init__(
        self, startNode: Node, endNode: Node, transportation: str, game_session_id: str
    ) -> None:
        self.startNode = startNode
        self.endNode = endNode
        self.transportation = transportation
        self.game_session_id = game_session_id

        game_session = 

        if transportation == "car":
            self.transportation_obj = CarMobility.objects.create(game_session_id)
        elif transportation == "public":
            self.transportation_obj = PublicMobility()
        elif transportation == "bus":
            self.transportation_obj = BusMobility()
        elif transportation == "train":
            self.transportation_obj = TrainMobility()
        elif transportation == "bike":
            self.transportation_obj = BikeMobility()
        else:
            self.transportation_obj = WalkingMobility()
