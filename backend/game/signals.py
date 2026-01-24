import logging

from co2mmute.utils import clear_chat_messages, round_complete, send_chat_system_message
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import Signal, receiver

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
    game_session = instance.game_round.game
    total_players = Player.objects.filter(game=game_session).count()
    completed_moves = PlayerMove.objects.filter(
        game_session=game_session, game_round=instance.game_round
    ).count()
    if round_complete(
        completed_moves,
        total_players,
    ):
        logger.info(
            f"Round {instance.game_round.round_number} complete for GameSession {game_session.game_id}"
        )
        round_completed.send(
            sender=GameSession,
            game_session=game_session,
            game_round=instance.game_round,
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
        # TODO: notify game consumer about new player


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

    last_move = (
        PlayerMove.objects.filter(player=instance).order_by("-game_round").first()
    )
    last_round = (
        GameRound.objects.filter(game=game_session).order_by("-round_number").first()
    )
    # Check if the leaving player hadn't submitted a move for the current round
    # and their departure completes the round
    if (
        last_move
        and last_round
        and last_round.round_number != last_move.game_round.round_number
        and game_session.is_active
    ):
        total_players = Player.objects.filter(game=game_session).count()
        completed_moves = PlayerMove.objects.filter(
            game_session=game_session, game_round=last_round
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
    # TODO: notify game consumer about leaving player
