import logging
import random

from co2mmute.utils import (
    clear_chat_messages,
    round_complete,
    send_chat_system_message,
    send_game_state_message,
)
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import Signal, receiver
from django.utils import timezone

from game.cache import cache_game_session, invalidate_game_session
from game.models import GameRound, GameSession, Player, PlayerMove

logger = logging.getLogger(__name__)


round_completed = Signal()


@receiver(pre_save, sender=GameSession)
def clear_chat_on_toggle(sender, instance: GameSession, **kwargs):
    if not instance.pk:
        return

    try:
        old_instance = GameSession.objects.get(pk=instance.pk)
        if old_instance.chat_enabled != instance.chat_enabled:
            clear_chat_messages(instance.game_id)
            logger.info(
                f"Chat {'enabled' if instance.chat_enabled else 'disabled'} for game {instance.game_id}, messages cleared"
            )
    except GameSession.DoesNotExist:
        pass


@receiver(post_save, sender=GameSession)
def cache_session_when_live(sender, instance: GameSession, **kwargs):
    cache_game_session(instance)


@receiver(post_delete, sender=GameSession)
def clear_session_cache(sender, instance: GameSession, **kwargs):
    invalidate_game_session(instance.game_id)


@receiver(post_save, sender=PlayerMove, dispatch_uid="check_round_completion")
def check_round_completion(sender, instance: PlayerMove, **kwargs):
    game_session = instance.session_round.game
    total_players = Player.objects.filter(game=game_session).count()
    completed_moves = PlayerMove.objects.filter(
        session_round=instance.session_round
    ).count()
    if round_complete(
        completed_moves,
        total_players,
    ):
        logger.info(
            f"Round {instance.session_round.round_number} complete for GameSession {game_session.game_id}"
        )
        round_completed.send(
            sender=GameSession,
            game_session=game_session,
            game_round=instance.session_round,
        )


@receiver(post_save, sender=Player)
def set_up_player(sender, instance: Player, created: bool, **kwargs):
    if created:
        game_session = instance.game
        logger.info(
            f"New Player {instance.player_id} added to GameSession {game_session.game_id}"
        )
        player_name = instance.name or "A new player"
        send_chat_system_message(game_session.game_id, f"{player_name} joined the game")

        # Assign home and destination nodes if game has a map
        agent_assignments = None
        if game_session.game_map:
            agent_assignments = assign_agent_nodes(game_session, instance)
            if agent_assignments:
                # Save without triggering another signal
                Player.objects.filter(pk=instance.pk).update(
                    agent_assignments=agent_assignments
                )
                logger.info(
                    f"Assigned home node {agent_assignments.get('home_node')} "
                    f"with {len(agent_assignments.get('agents', []))} destinations "
                    f"to player {instance.player_id}"
                )

        # Notify game consumer about new player
        send_game_state_message(
            game_session.game_id,
            "player.joined",
            {
                "player_id": instance.player_id,
                "player_name": player_name,
                "controlled_by_host": instance.controlled_by_host,
                "agent_assignments": agent_assignments,
            },
        )


def assign_agent_nodes(game_session: GameSession, player: Player) -> dict | None:
    """
    Assign a home node and destination nodes for each agent.
    Each player gets a unique home node (all their agents share it).
    Returns dict with home_node and agents list, or None if map not available.
    """
    from maps.models import MapVersion, Node

    game_map = game_session.game_map
    if not game_map:
        return None

    # Get base version of the map
    base_version = MapVersion.objects.filter(game_map=game_map, base_version=True).first()
    if not base_version:
        logger.warning(f"No base version found for map {game_map.pk}")
        return None

    # Get all home nodes in this map version
    home_nodes = set(
        Node.objects.filter(
            game_map=game_map,
            map_versions=base_version,
            node_type__name="home",
        ).values_list("id", flat=True)
    )

    # Get all destination nodes (workplace, school, etc.)
    destination_nodes = list(
        Node.objects.filter(
            game_map=game_map,
            map_versions=base_version,
            node_type__name__in=["workplace", "station", "bus_stop"],
        ).values_list("id", flat=True)
    )

    if not home_nodes:
        logger.warning(f"No home nodes found for map {game_map.pk}")
        return None

    if not destination_nodes:
        logger.warning(f"No destination nodes found for map {game_map.pk}")
        return None

    # Get home nodes already assigned to other players in this game
    other_players = Player.objects.filter(game=game_session).exclude(pk=player.pk)
    used_home_nodes = set()
    for other_player in other_players:
        if other_player.agent_assignments and "home_node" in other_player.agent_assignments:
            used_home_nodes.add(other_player.agent_assignments["home_node"])

    # Pick from available (unused) home nodes
    available_home_nodes = list(home_nodes - used_home_nodes)
    if not available_home_nodes:
        # Fall back to any home node if all are taken (more players than home nodes)
        logger.warning(f"All home nodes taken for game {game_session.game_id}, reusing")
        available_home_nodes = list(home_nodes)

    home_node_id = random.choice(available_home_nodes)

    # Pick destination nodes for each agent (with replacement if not enough unique nodes)
    agent_count = game_session.agent_per_player
    agents = []

    # Shuffle destinations for variety
    shuffled_destinations = destination_nodes.copy()
    random.shuffle(shuffled_destinations)

    for i in range(agent_count):
        # Cycle through destinations if we have fewer than agent_count
        dest_node_id = shuffled_destinations[i % len(shuffled_destinations)]
        agents.append({
            "id": i + 1,
            "destination_node": dest_node_id,
        })

    return {
        "home_node": home_node_id,
        "agents": agents,
    }


@receiver(post_delete, sender=Player)
def cleanup_leaving_player(sender, instance: Player, **kwargs):
    game_session = instance.game
    player_name = instance.name or "A player"
    was_kicked = getattr(instance, "_was_kicked", False)

    if was_kicked:
        send_chat_system_message(
            game_session.game_id, f"{player_name} was removed from the game"
        )
    else:
        send_chat_system_message(game_session.game_id, f"{player_name} left the game")

    # Notify game consumer about leaving player
    send_game_state_message(
        game_session.game_id,
        "player.left",
        {
            "player_id": instance.player_id,
            "player_name": player_name,
            "was_kicked": was_kicked,
        },
    )

    last_move = (
        PlayerMove.objects.filter(player=instance).order_by("-session_round").first()
    )
    last_round = (
        GameRound.objects.filter(game=game_session).order_by("-round_number").first()
    )
    if (
        last_move
        and last_round
        and last_round.round_number != last_move.session_round.round_number
        and game_session.is_active
    ):
        total_players = Player.objects.filter(game=game_session).count()
        completed_moves = PlayerMove.objects.filter(
            session_round=last_round
        ).count()
        if round_complete(completed_moves, total_players):
            logger.info(
                f"Round {last_round.round_number} complete for GameSession {game_session.game_id} after Player {instance.player_id} deletion"
            )
            round_completed.send(
                sender=GameSession,
                game_session=game_session,
                game_round=last_round,
            )


@receiver(post_save, sender=GameSession)
def game_start(sender, instance: GameSession, created=False, **kwargs):
    if not isinstance(instance, GameSession):
        return

    if instance.is_active and instance.started_at:
        current_round = (
            GameRound.objects.filter(game=instance).order_by("-round_number").first()
        )
        round_number = current_round.round_number if current_round else 1

        send_game_state_message(
            instance.game_id,
            "game.started",
            {
                "game_name": instance.game_name,
                "max_rounds": instance.max_rounds,
                "max_co2_level": instance.max_CO2_level,
                "current_round": round_number,
                "started_at": instance.started_at.isoformat() if instance.started_at else None,
            },
        )
        logger.info(f"Game {instance.game_id} started, notified players")

    elif instance.ended_at:
        total_emissions = sum(
            r.total_emissions_g for r in GameRound.objects.filter(game=instance)
        )
        final_round = (
            GameRound.objects.filter(game=instance).order_by("-round_number").first()
        )

        co2_limit_reached = total_emissions >= (instance.max_CO2_level * 1000)

        send_game_state_message(
            instance.game_id,
            "game.ended",
            {
                "reason": "co2_limit" if co2_limit_reached else "max_rounds",
                "final_round": final_round.round_number if final_round else 0,
                "total_emissions_g": total_emissions,
                "max_co2_level_g": instance.max_CO2_level * 1000,
                "ended_at": instance.ended_at.isoformat() if instance.ended_at else None,
            },
        )
        logger.info(f"Game {instance.game_id} ended, notified players")


@receiver(round_completed)
def handle_round_completed(sender, game_id=None, game_session=None, game_round=None, **kwargs):
    """
    Handle round completion: calculate stats, check end conditions, create new round or end game.

    For dry run: uses hardcoded emission values per action type.
    """
    # Resolve game_session from either direct reference or game_id
    if game_session is None and game_id:
        try:
            game_session = GameSession.objects.get(game_id=game_id)
        except GameSession.DoesNotExist:
            logger.error(f"Game {game_id} not found in round_completed handler")
            return

    if game_session is None:
        logger.error("No game_session provided to round_completed handler")
        return

    # Get the current round
    if game_round is None:
        game_round = (
            GameRound.objects.filter(game=game_session)
            .order_by("-round_number")
            .first()
        )

    if game_round is None:
        logger.error(f"No round found for game {game_session.game_id}")
        return

    # Mark round as completed
    game_round.status = GameRound.Status.COMPLETED
    game_round.save(update_fields=["status", "updated_at"])

    # Calculate round stats with hardcoded values for dry run
    # Values: car=150g, public=30g, bike=5g, walk=0g per move
    HARDCODED_EMISSIONS = {
        "car": 150.0,
        "public": 30.0,
        "bike": 5.0,
        "walk": 0.0,
    }
    HARDCODED_COSTS = {
        "car": 5.0,
        "public": 2.5,
        "bike": 0.5,
        "walk": 0.0,
    }
    HARDCODED_TIME = {
        "car": 15,  # minutes
        "public": 25,
        "bike": 20,
        "walk": 45,
    }

    moves = PlayerMove.objects.filter(session_round=game_round)
    round_emissions = 0.0
    round_cost = 0.0
    player_stats = []

    for move in moves:
        # Check if move has per-agent choices in payload
        payload = move.payload or {}
        agents = payload.get("agents", [])

        if agents:
            # Calculate emissions for all agents
            player_emissions = 0.0
            player_cost = 0.0
            player_time = 0
            actions_used = []

            for agent in agents:
                agent_action = agent.get("action", move.action)
                player_emissions += HARDCODED_EMISSIONS.get(agent_action, 0.0)
                player_cost += HARDCODED_COSTS.get(agent_action, 0.0)
                player_time += HARDCODED_TIME.get(agent_action, 0)
                actions_used.append(agent_action)

            # Summarize actions for display
            action_summary = ", ".join(set(actions_used)) if len(set(actions_used)) > 1 else actions_used[0] if actions_used else move.action
        else:
            # Fallback to single action (legacy mode)
            action = move.action
            player_emissions = HARDCODED_EMISSIONS.get(action, 0.0)
            player_cost = HARDCODED_COSTS.get(action, 0.0)
            player_time = HARDCODED_TIME.get(action, 0)
            action_summary = action

        round_emissions += player_emissions
        round_cost += player_cost

        player_stats.append({
            "player_id": move.player.player_id,
            "player_name": move.player.name or "Player",
            "action": action_summary,
            "emissions_g": player_emissions,
            "cost_eur": player_cost,
            "time_min": player_time,
        })

    # Update round totals
    game_round.total_emissions_g = round_emissions
    game_round.total_cost_eur = round_cost
    game_round.save(update_fields=["total_emissions_g", "total_cost_eur", "updated_at"])

    # Calculate cumulative emissions across all rounds
    total_game_emissions = sum(
        r.total_emissions_g
        for r in GameRound.objects.filter(game=game_session, status=GameRound.Status.COMPLETED)
    )

    # Broadcast round completed stats
    send_game_state_message(
        game_session.game_id,
        "round.completed",
        {
            "round_number": game_round.round_number,
            "round_emissions_g": round_emissions,
            "round_cost_eur": round_cost,
            "total_game_emissions_g": total_game_emissions,
            "max_co2_level_g": game_session.max_CO2_level * 1000,
            "player_stats": player_stats,
        },
    )
    logger.info(
        f"Round {game_round.round_number} completed for game {game_session.game_id}: "
        f"{round_emissions}g CO2, €{round_cost}"
    )

    # Check game end conditions
    co2_limit_reached = total_game_emissions >= (game_session.max_CO2_level * 1000)
    max_rounds_reached = game_round.round_number >= game_session.max_rounds

    if co2_limit_reached or max_rounds_reached:
        # End the game
        game_session.is_active = False
        game_session.ended_at = timezone.now()
        game_session.save(update_fields=["is_active", "ended_at", "updated_at"])
        logger.info(
            f"Game {game_session.game_id} ended: "
            f"{'CO2 limit reached' if co2_limit_reached else 'max rounds reached'}"
        )
        # The game_start signal handler will broadcast game.ended
        return

    # Create new round
    new_round_obj = GameRound.objects.create(
        game=game_session,
        status=GameRound.Status.ACTIVE,
        started_at=timezone.now(),
    )

    # Broadcast new round started
    send_game_state_message(
        game_session.game_id,
        "round.started",
        {
            "round_number": new_round_obj.round_number,
            "max_rounds": game_session.max_rounds,
            "total_game_emissions_g": total_game_emissions,
            "max_co2_level_g": game_session.max_CO2_level * 1000,
        },
    )
    logger.info(f"Round {new_round_obj.round_number} started for game {game_session.game_id}")
