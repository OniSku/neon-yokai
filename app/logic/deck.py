import random

from app.schemas.battle import BattleState, CardInstance


async def shuffle_discard_into_draw(state: BattleState) -> None:
    state.draw_pile.extend(state.discard_pile)
    state.discard_pile.clear()
    random.shuffle(state.draw_pile)


HAND_LIMIT: int = 10


async def draw_cards(state: BattleState, count: int | None = None) -> None:
    count = count or state.hand_size

    for card in state.retained_cards[:]:
        if len(state.hand) < HAND_LIMIT:
            state.hand.append(card)
            state.retained_cards.remove(card)

    for _ in range(count):
        if len(state.hand) >= HAND_LIMIT:
            break

        if not state.draw_pile:
            if not state.discard_pile:
                break
            await shuffle_discard_into_draw(state)

        if state.draw_pile:
            state.hand.append(state.draw_pile.pop())


async def discard_hand(state: BattleState) -> None:
    state.discard_pile.extend(state.hand)
    state.hand.clear()


async def play_card(state: BattleState, hand_index: int) -> CardInstance:
    if hand_index < 0 or hand_index >= len(state.hand):
        raise ValueError("Invalid hand index")

    card = state.hand.pop(hand_index)

    if card.is_exhaust:
        state.exhaust_pile.append(card)
    else:
        state.discard_pile.append(card)

    return card


async def init_deck(state: BattleState, cards: list[CardInstance]) -> None:
    state.draw_pile = list(cards)
    random.shuffle(state.draw_pile)
    state.hand.clear()
    state.discard_pile.clear()
    state.exhaust_pile.clear()
    state.retained_cards.clear()
