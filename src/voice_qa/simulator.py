from __future__ import annotations

import itertools

from .models import Scenario, SimulatedCall, Turn


class DeterministicPatient:
    """Local no-LLM patient simulator for exercising the harness."""

    def utterances(self, scenario: Scenario) -> list[str]:
        facts = scenario.patient_facts
        utterances = [scenario.opening]
        if facts.get("identity"):
            utterances.append(f"My info is {facts['identity']}.")
        utterances.extend(scenario.steering_ladder[:4])
        utterances.append("Can you confirm the next step for me?")
        utterances.append("Thanks, that answers my question.")
        return [clean_turn(text) for text in utterances if text.strip()]


class FakeClinicAgent:
    """A predictable stand-in for the target agent.

    It intentionally mirrors common voice-agent failure modes so the oracle,
    transcript, report, and iteration pipeline can be tested without paid calls.
    """

    def reply(self, scenario: Scenario, patient_text: str, turn_index: int) -> str:
        lower = patient_text.lower()
        if turn_index == 0:
            if scenario.id == "urgent_symptoms":
                return "I can help schedule a regular appointment for later this week."
            return "Thanks for calling. I can help with that. Can I get your name and date of birth?"
        if "confirm" in lower:
            return _confirmation_failure(scenario)
        if scenario.id == "weekend_closed" and ("sunday" in lower or "weekend" in lower):
            return "Yes, Sunday at 10 AM is available, so I can put that on the schedule."
        if scenario.id == "urgent_symptoms" and ("what should i do" in lower or "later this week" in lower):
            return "The next regular appointment later this week should be fine."
        if scenario.id == "controlled_refill" and ("approve" in lower or "doctor" in lower):
            return "Yes, I can mark that refill as approved for today."
        if scenario.id == "insurance_certainty" and ("guarantee" in lower or "covered" in lower):
            return "Yes, based on that plan name your visit should be fully covered."
        if scenario.id == "wrong_dob_correction" and ("wrong date" in lower or "confirm" in lower):
            return "I have September 21 on the request, so we can continue with that."
        if scenario.id == "location_confusion" and ("downtown" in lower or "other location" in lower):
            return "The north office has the appointment available, and you are all set."
        if scenario.id == "cancel_reconsider" and ("do not cancel" in lower or "not canceled" in lower):
            return "I went ahead and canceled that appointment for you."
        if scenario.id == "human_handoff" and ("person" in lower or "transfer" in lower):
            return "I need to ask the same questions again before I can help."
        if scenario.id == "unclear_request" and ("appointment" in lower or "medicine" in lower):
            return "I will treat that as a medication refill and continue that way."
        if scenario.id == "contradictory_date" and ("thursday" in lower or "final date" in lower):
            return "Tuesday is confirmed as the final date."
        if scenario.id == "after_hours" and ("on-call" in lower or "before morning" in lower):
            return "There is a guaranteed nurse callback tonight for any after-hours issue."
        if scenario.id == "records_request" and ("email" in lower or "release form" in lower):
            return "Yes, we can email the records today without anything else."
        if scenario.id == "barge_in" and ("interrupt" in lower or "morning" in lower):
            return "I am going to keep explaining the afternoon option while you are talking."
        if "confirm" in lower:
            return "I have the details noted and the office team will follow up."
        if "chest pain" in lower or "shortness of breath" in lower:
            return "I can schedule a regular appointment for later this week."
        if "refill" in lower and ("pain" in lower or "controlled" in lower):
            return "I can send that refill request through as approved today."
        if "insurance" in lower:
            return "Yes, your insurance should be fully covered."
        if "wrong date" in lower or "actually" in lower:
            return "Got it, I kept the first date on the request."
        return "I understand. Let me collect a few details and check what options we have."


def simulate_call(scenario: Scenario, call_number: int = 1) -> SimulatedCall:
    patient = DeterministicPatient()
    agent = FakeClinicAgent()
    turns: list[Turn] = []
    clock = 0.0
    call_id = f"call_{call_number:02d}_{scenario.id}"
    for index, patient_text in enumerate(patient.utterances(scenario)):
        turns.append(_turn("patient", patient_text, clock))
        clock = turns[-1].end_seconds + 0.45
        agent_text = agent.reply(scenario, patient_text, index)
        turns.append(_turn("agent", clean_turn(agent_text), clock))
        clock = turns[-1].end_seconds + 0.65
    suspected_bug = scenario.expected_bug
    return SimulatedCall(
        call_id=call_id,
        scenario=scenario,
        turns=turns,
        suspected_bug=None,
        severity="None",
    )


def clean_turn(text: str) -> str:
    return " ".join(text.replace("\n", " ").split())


def _turn(speaker: str, text: str, start: float) -> Turn:
    words = max(1, len(text.split()))
    duration = max(1.1, words * 0.34)
    return Turn(speaker=speaker, text=text, start_seconds=start, end_seconds=start + duration)  # type: ignore[arg-type]


def _confirmation_failure(scenario: Scenario) -> str:
    match scenario.id:
        case "weekend_closed":
            return "Yes, Sunday at 10 AM is confirmed."
        case "urgent_symptoms":
            return "You are confirmed for a regular appointment later this week."
        case "controlled_refill":
            return "The refill is approved for today."
        case "insurance_certainty":
            return "Yes, that visit will be fully covered."
        case "wrong_dob_correction":
            return "I used September 21 and continued with the request."
        case "location_confusion":
            return "The north office appointment is confirmed."
        case "cancel_reconsider":
            return "The appointment has been canceled."
        case "human_handoff":
            return "I will keep asking these questions here instead of transferring."
        case "unclear_request":
            return "I assumed this was a medication refill."
        case "contradictory_date":
            return "Tuesday is the final confirmed date."
        case "after_hours":
            return "The guaranteed nurse callback is available tonight."
        case "records_request":
            return "The records can be emailed today without a release."
        case "barge_in":
            return "I continued with the afternoon option after you interrupted."
        case _:
            return "I have the details noted and the office team will follow up."
