from vidliboom import script, planner


SRC = """# Test Episode
## Scene: One | bg=sky | mood=rain
BABLU [wave]: Namaste!
DIDI: Hello Bablu, kaise ho?
(stage direction)
## Scene: Two | mood=night
UNCLE [zen]: Shubh ratri.
"""


def test_parse():
    s = script.parse(SRC)
    assert s.title == "Test Episode"
    assert [sc.mood for sc in s.scenes] == ["rain", "night"]
    l0 = s.scenes[0].lines[0]
    assert (l0.speaker, l0.pose, l0.text) == ("BABLU", "wave", "Namaste!")
    assert s.scenes[0].lines[1].pose == "idle"
    assert s.scenes[0].directions == ["stage direction"]


def test_plan_without_voice():
    shots, total = planner.plan(script.parse(SRC))
    assert len(shots) == 3
    assert all(b.start >= a.start + a.duration - 1e-9 for a, b in zip(shots, shots[1:]))
    assert total > shots[-1].start
