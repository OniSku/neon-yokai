import pytest

from app.logic.deck import discard_hand, draw_cards, init_deck, play_card, shuffle_discard_into_draw
from app.schemas.battle import BattleState, CardInstance


def _make_card(name: str = "TestCard", **kwargs) -> CardInstance:
    return CardInstance(card_id=0, name=name, **kwargs)


def _make_state(cards: list[CardInstance] | None = None) -> BattleState:
    state = BattleState(user_id=1, hand_size=3)
    if cards:
        state.draw_pile = list(cards)
    return state


@pytest.mark.asyncio
async def test_init_deck_shuffles_and_clears() -> None:
    cards = [_make_card(name=f"C{i}") for i in range(10)]
    state = _make_state()
    state.hand = [_make_card(name="leftover")]
    state.discard_pile = [_make_card(name="old")]

    await init_deck(state, cards)

    assert len(state.draw_pile) == 10
    assert len(state.hand) == 0
    assert len(state.discard_pile) == 0
    assert len(state.exhaust_pile) == 0


@pytest.mark.asyncio
async def test_draw_cards_moves_from_draw_to_hand() -> None:
    state = _make_state([_make_card(name=f"C{i}") for i in range(5)])

    await draw_cards(state, count=3)

    assert len(state.hand) == 3
    assert len(state.draw_pile) == 2


@pytest.mark.asyncio
async def test_draw_cards_uses_hand_size_default() -> None:
    state = _make_state([_make_card() for _ in range(10)])
    state.hand_size = 5

    await draw_cards(state)

    assert len(state.hand) == 5


@pytest.mark.asyncio
async def test_draw_cards_reshuffles_discard_when_draw_empty() -> None:
    state = _make_state()
    state.draw_pile = [_make_card(name="last")]
    state.discard_pile = [_make_card(name=f"D{i}") for i in range(4)]

    await draw_cards(state, count=3)

    assert len(state.hand) == 3
    assert len(state.discard_pile) == 0


@pytest.mark.asyncio
async def test_draw_cards_stops_when_both_piles_empty() -> None:
    state = _make_state()
    state.draw_pile = [_make_card()]

    await draw_cards(state, count=5)

    assert len(state.hand) == 1


@pytest.mark.asyncio
async def test_discard_hand_moves_all_to_discard() -> None:
    state = _make_state()
    state.hand = [_make_card() for _ in range(3)]

    await discard_hand(state)

    assert len(state.hand) == 0
    assert len(state.discard_pile) == 3


@pytest.mark.asyncio
async def test_play_card_normal_goes_to_discard() -> None:
    card = _make_card(name="Strike", is_exhaust=False)
    state = _make_state()
    state.hand = [card]

    played = await play_card(state, 0)

    assert played.name == "Strike"
    assert len(state.hand) == 0
    assert len(state.discard_pile) == 1
    assert len(state.exhaust_pile) == 0


@pytest.mark.asyncio
async def test_play_card_exhaust_goes_to_exhaust() -> None:
    card = _make_card(name="Burn", is_exhaust=True)
    state = _make_state()
    state.hand = [card]

    played = await play_card(state, 0)

    assert played.name == "Burn"
    assert len(state.discard_pile) == 0
    assert len(state.exhaust_pile) == 1


@pytest.mark.asyncio
async def test_play_card_invalid_index_raises() -> None:
    state = _make_state()
    state.hand = [_make_card()]

    with pytest.raises(ValueError, match="Invalid hand index"):
        await play_card(state, 5)


@pytest.mark.asyncio
async def test_shuffle_discard_into_draw() -> None:
    state = _make_state()
    state.discard_pile = [_make_card(name=f"D{i}") for i in range(5)]

    await shuffle_discard_into_draw(state)

    assert len(state.draw_pile) == 5
    assert len(state.discard_pile) == 0
