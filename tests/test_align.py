"""scripts/align.py: pure viseme mapping / smoothing / per-frame track tests (no model needed),
plus one MMS_FA end-to-end test that is skipped unless torch, torchaudio, uroman and the cached weights exist."""
import json, os, subprocess, sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import align  # noqa: E402


def test_char_shapes():
    assert [align.char_shape(c) for c in 'aoueimbpwy'] == ['A', 'O', 'O', 'E', 'E', 'M', 'M', 'M', 'O', 'E']
    assert align.char_shape('k') is None and align.char_shape('s') is None


def test_split_words_drops_punct_tokens():
    assert align.split_words('gir rahe ho... aur — ekdum!') == ['gir', 'rahe', 'ho', 'aur', 'ekdum!']
    assert align.split_words('नमस्ते दोस्तों। आज') == ['नमस्ते', 'दोस्तों।', 'आज']


def test_clean_roman():
    assert align.clean_roman('Kahīn, 2 BAAR!') == 'kahinbaar'


def test_fix_nasals():
    assert align._fix_nasals('दोस्तों') == 'दोस्तोन्'      # anusvara -> n (no lip closure)
    assert align._fix_nasals('अंबा') == 'अम्बा'            # before a labial -> m
    assert align._fix_nasals('हूँ') == 'हू'                # chandrabindu dropped


def test_word_segments_coarticulation():
    # "kab": k takes next vowel (A), a -> A, b -> M ; boundaries at letter starts, last to word end
    segs = align.word_segments('kab', [1.0, 1.05, 1.2], 1.3)
    assert segs == [(1.0, 1.05, 'A'), (1.05, 1.2, 'A'), (1.2, 1.3, 'M')]
    # consonant at the end takes the previous vowel
    assert align.word_segments('ek', [0.0, .1], .2)[-1][2] == 'E'


def test_smooth_min_hold_merges_flicker():
    segs = [(0, .2, 'A'), (.2, .23, 'E'), (.23, .5, 'O')]
    out = align.smooth(segs, .06)
    assert all(b - a >= .06 - 1e-9 for a, b, _ in out)
    assert [s for *_, s in out] == ['A', 'O']
    assert out[0][0] == 0 and out[-1][1] == .5           # contiguous, same total span


def test_smooth_stretches_short_closure():
    out = align.smooth([(0, .3, 'A'), (.3, .32, 'M'), (.32, .6, 'A')], .06)
    assert [s for *_, s in out] == ['A', 'M', 'A']
    m = out[1]; assert abs((m[1] - m[0]) - .06) < 1e-9 and abs((m[0] + m[1]) / 2 - .31) < 1e-9


def test_visemes_from_chars_pauses_and_rest():
    words = [{'start': .5, 'end': .8, 'chars': [('a', .5), ('a', .6), ('p', .7)]},
             {'start': .85, 'end': 1.1, 'chars': [('h', .85), ('o', .9)]},       # 50 ms gap: mouth stays
             {'start': 1.6, 'end': 1.9, 'chars': [('i', 1.6)]}]                    # 500 ms pause -> rest
    v = align.visemes_from_chars(words, 2.5)
    assert v[0] == {'t': 0.0, 'shape': 'rest'} and v[-1]['shape'] == 'rest'
    shapes = [x['shape'] for x in v]
    assert shapes == ['rest', 'A', 'M', 'O', 'rest', 'E', 'rest']
    t = {x['shape']: x['t'] for x in v if x['shape'] in 'AE'}
    assert t == {'A': .5, 'E': 1.6}
    assert all(b['t'] - a['t'] >= .06 - 1e-6 for a, b in zip(v, v[1:]))


def test_load_mouth_track_and_fallback():
    d = {'duration': 1.0, 'visemes': [{'t': 0, 'shape': 'rest'}, {'t': .2, 'shape': 'M'}, {'t': .3, 'shape': 'E'},
                                       {'t': .6, 'shape': 'rest'}]}
    tr = align.load_mouth_track(d, 10)
    assert len(tr) == 11 and tr[:2] == ['rest', 'rest'] and tr[2] == 'M' and tr[3:6] == ['E'] * 3 and tr[6] == 'rest'
    rig = align.load_mouth_track(d, 10, available={'rest', 'A', 'O'})
    assert rig[2] == 'rest' and rig[3] == 'A'           # M -> rest, E -> A when the rig lacks those patches
    assert align.load_mouth_track(d, 10, lead=.1)[1] == 'M'   # lead shows shapes one frame early


def test_load_mouth_track_from_path(tmp_path):
    p = tmp_path / 'a.json'; p.write_text(json.dumps({'duration': .2, 'visemes': [{'t': 0, 'shape': 'A'}]}))
    assert align.load_mouth_track(str(p), 10) == ['A', 'A', 'A']


def test_redistribute_and_caption_words():
    al = [{'w': 'नमस्ते', 'start': .3, 'end': .7}, {'w': 'दोस्तों', 'start': .9, 'end': 1.3}]
    assert align.redistribute(['Namaste', 'dosto'], al)[1] == {'w': 'dosto', 'start': .9, 'end': 1.3}
    sp = align.redistribute(['Hello', 'sab', 'log'], al)
    assert sp[0]['start'] == .3 and sp[-1]['end'] <= 1.3 and len(sp) == 3
    assert align.caption_words({'words': al})[0] == {'word': 'नमस्ते', 'start': .3, 'end': .7}


def test_fill_missing():
    ws = align.fill_missing([{'w': 'a', 'start': 0., 'end': .5}, {'w': '2', 'start': None, 'end': None},
                             {'w': 'b', 'start': 1., 'end': 1.4}])
    assert ws[1]['start'] == .5 and ws[1]['end'] == 1.


def test_is_fresh(tmp_path):
    T = {'segs': [{'start': .5, 'end': 2.}, {'start': 2.3, 'end': 4.}]}
    p = tmp_path / 'align.json'; p.write_text(json.dumps({'segs': [[.5, 2.], [2.3, 4.]]}))
    assert align.is_fresh(str(p), T)
    T['segs'][1]['end'] = 4.5
    assert not align.is_fresh(str(p), T)


@pytest.mark.skipif(not (align.mms_available(download=False) and align.weights_cached()),
                    reason='MMS_FA weights / torch / uroman not installed')
def test_mms_alignment_tone_clip(tmp_path):
    """Smoke test without TTS: alignment runs on synthetic audio and returns ordered, in-range times."""
    wav = tmp_path / 'tone.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=f=220:d=2', '-ar', '16000', '-ac', '1', str(wav)], check=True)
    r = align.align_clip(str(wav), 'aap kaise ho', method='mms')
    assert r['method'] == 'mms_fa' and len(r['words']) == 3
    st = [w['start'] for w in r['words']]
    assert st == sorted(st) and 0 <= st[0] and r['words'][-1]['end'] <= 2.05
