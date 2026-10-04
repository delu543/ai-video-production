import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills/ai-video-production/scripts"
sys.path.insert(0, str(SCRIPTS))
from core import binary, fingerprint, media_path, read_json, run, timing, validate
from captions import create, escape_ass
from audio import mix
from render import render, frame_count
from qa import audit, review_frames
from costs import reserve, settle
from video import init_project
from render import encode_args
import tts


def fixture():
    p = read_json(ROOT / "skills/ai-video-production/assets/project.example.json")
    p["profile"].update(width=640, height=360, fade_in=0, fade_out=0)
    p["facts"] = []
    p["beats"] = [{"id": "b1", "narration": "Engineering test only.", "fact_ids": []},
                  {"id": "b2", "narration": "A related detail.", "fact_ids": []}]
    p["assets"] = {}
    for aid, kind, w, h in [("wide", "video", 640, 360), ("portrait", "video", 360, 640), ("photo", "still", 640, 360)]:
        p["assets"][aid] = {"kind": kind, "path": f"assets/{aid}.{'png' if kind == 'still' else 'mp4'}",
                               "origin": "synthetic_test", "source_group": aid,
                               "source_url": f"urn:test:{aid}", "creator": "local test generator",
                               "duration": 5, "rights_status": "cleared", "rights_basis": "self-created test fixture",
                               "quality": {"effective_width": w, "effective_height": h, "review": "passed"}}
    for aid in ["voice", "music"]:
        p["assets"][aid] = {"kind": "audio", "path": f"audio/{aid}.wav", "origin": "synthetic_test",
                               "source_url": f"urn:test:{aid}", "creator": "local sine generator",
                               "duration": 5, "rights_status": "cleared", "rights_basis": "self-created test fixture"}
    p["shots"] = [
        {"id": "s1", "asset_id": "wide", "beat_id": "b1", "purpose": "test wide picture", "source_in": .2,
         "duration": 1.4, "framing": "cover", "transition": {"type": "cut", "duration": 0}},
        {"id": "s2", "asset_id": "portrait", "beat_id": "b2", "purpose": "test preserved portrait", "source_in": .3,
         "duration": 1.7, "framing": "contain", "transition": {"type": "dissolve", "duration": .3, "relation": "related detail"}},
        {"id": "s3", "asset_id": "photo", "beat_id": "b2", "purpose": "test meaningful still", "duration": 1.5,
         "framing": "cover", "zoom": .02, "transition": {"type": "dissolve", "duration": .4, "relation": "same object in another medium"}}]
    p["captions"] = [{"start": .1, "end": 1.1, "top": "真实素材工作流测试", "bottom": "Workflow test."},
                     {"start": 1.4, "end": 3.5, "top": "中文在上\n测试两行", "bottom": "Chinese above English.\nTwo-line layout test."}]
    p["audio_cues"] = [{"id": "n1", "asset_id": "voice", "role": "narration", "start": 0,
                         "source_in": 0, "duration": 3.9, "gain_db": 0, "fade_in": .02, "fade_out": .1},
                        {"id": "m1", "asset_id": "music", "role": "music", "start": 0, "source_in": 0,
                         "duration": 3.9, "selection_reason": "test music automation, not real score",
                         "gain_db": -20, "envelope": [[0, -20], [1, -26], [3.4, -22], [3.9, -30]],
                         "fade_in": .3, "fade_out": .3}]
    return p


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.p = fixture()

    def tearDown(self):
        self.tmp.cleanup()

    def check(self):
        return validate(self.p, self.root, allow_test=True)

    def test_valid_design_and_global_frames(self):
        report = self.check()
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["frames"], 117)
        self.assertAlmostEqual(report["duration"], 3.9)

    def test_synthetic_is_not_production_media(self):
        self.assertFalse(validate(self.p, self.root)["ok"])

    def test_unrelated_cut_rejected(self):
        self.p["shots"][1]["transition"] = {"type": "cut", "duration": 0}
        self.assertTrue(any("relation missing" in e for e in self.check()["errors"]))

    def test_related_direct_cut_requires_reason(self):
        self.p["shots"][1]["transition"] = {"type": "cut", "duration": 0, "relation": "continuous action"}
        self.assertTrue(any("cut needs" in e for e in self.check()["errors"]))

    def test_source_interval_rejected(self):
        self.p["shots"][0]["source_in"] = 4.7
        self.assertTrue(any("source interval" in e for e in self.check()["errors"]))

    def test_effective_resolution_not_nominal_label(self):
        self.p["assets"]["wide"]["quality"].update(effective_width=160, effective_height=90)
        self.assertTrue(any("upscale" in e for e in self.check()["errors"]))

    def test_aliases_cannot_hide_source_reuse(self):
        for asset in self.p["assets"].values():
            asset["source_group"] = "one_original_file"
        self.assertTrue(any("3 uses" in e for e in self.check()["errors"]))

    def test_short_shot_cannot_be_eaten_by_two_transitions(self):
        self.p["shots"][1]["duration"] = .6
        self.assertFalse(self.check()["ok"])

    def test_caption_overlap_rejected(self):
        self.p["captions"][1]["start"] = .9
        self.assertTrue(any("Caption overlaps" in e for e in self.check()["errors"]))

    def test_unverified_fact_blocks_design(self):
        self.p["facts"] = [{"id": "f1", "claim": "An unchecked claim", "status": "pending", "sources": []}]
        self.p["beats"][0]["fact_ids"] = ["f1"]
        self.assertFalse(self.check()["ok"])

    def test_generated_visuals_rejected(self):
        self.p["assets"]["wide"]["origin"] = "generated"
        self.assertTrue(any("generated visuals forbidden" in e for e in self.check()["errors"]))

    def test_still_permission_does_not_allow_generated_video(self):
        self.p["quality"]["allow_generated_visuals"] = True
        self.p["assets"]["wide"]["origin"] = "generated"
        self.assertTrue(any("generated video forbidden" in e for e in self.check()["errors"]))

    def test_authorized_still_switch_is_technical_only(self):
        self.p["quality"]["allow_generated_visuals"] = True
        self.p["assets"]["photo"]["origin"] = "generated"
        self.assertTrue(self.check()["ok"])

    def test_explicit_single_language_caption_needs_no_empty_second_track(self):
        self.p["profile"]["bottom_language"] = ""
        for cue in self.p["captions"]:
            cue.pop("bottom")
        self.assertTrue(self.check()["ok"])
        ass, srt = create(self.p, self.root)
        self.assertFalse(any(",Bottom," in line for line in ass.read_text().splitlines() if line.startswith("Dialogue:")))
        self.assertNotIn("Workflow test.", srt.read_text())

    def test_bilingual_profile_still_requires_second_language(self):
        self.p["captions"][0]["bottom"] = ""
        self.assertTrue(any("Caption bottom: required" in e for e in self.check()["errors"]))

    def test_caption_anchor_overrides_keep_assumptions_clear(self):
        self.p["profile"].update(bottom_language="", caption_top_y_ratio=.95)
        for cue in self.p["captions"]:
            cue.pop("bottom")
        self.p["captions"][0]["caption_top_y_ratio"] = .92
        self.assertTrue(self.check()["ok"])
        ass, _ = create(self.p, self.root)
        text = ass.read_text()
        self.assertIn(r"\pos(320,331)", text)
        self.assertIn(r"\pos(320,342)", text)

    def test_caption_anchor_outside_frame_rejected(self):
        self.p["captions"][0]["caption_top_y_ratio"] = 1.1
        self.assertFalse(self.check()["ok"])
        with self.assertRaises(ValueError):
            create(self.p, self.root)

    def test_generated_music_rejected_but_narration_allowed(self):
        self.p["assets"]["voice"]["origin"] = "generated"
        self.assertTrue(self.check()["ok"])
        self.p["assets"]["music"]["origin"] = "generated"
        self.assertTrue(any("AI music" in e for e in self.check()["errors"]))

    def test_unknown_rights_block_publish(self):
        self.p["assets"]["wide"]["rights_status"] = "needs_review"
        report = validate(self.p, self.root, "publish", allow_test=True)
        self.assertTrue(any("rights not cleared" in e for e in report["errors"]))

    def test_caption_anchors_and_override_sanitization(self):
        ass, srt = create(self.p, self.root)
        text = ass.read_text()
        self.assertIn("中文在上\\N测试两行", text)
        self.assertIn("真实素材工作流测试", srt.read_text())
        self.assertNotIn("{\\pos", escape_ass("{\\pos(0,0)}injection"))
        self.assertIn("Style: Top", text)
        self.assertIn("Style: Bottom", text)

    def test_path_traversal_and_symlink_escape(self):
        with self.assertRaises(ValueError):
            media_path(self.root, "../outside.mp4")
        link = self.root / "link"
        link.symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaises(ValueError):
            media_path(self.root, "link/outside.mp4")

    def test_unknown_charge_and_duplicate_action_are_not_retried(self):
        self.p["budget"] = {"cap": 1, "currency": "CNY", "authorization": "test-only budget, no real API"}
        reserve(self.root, self.p, "a", "test", "input1", .6, "test pricing")
        for action, fingerprint_value, maximum in [("a", "other", .1), ("b", "input1", .1), ("b", "other", .5)]:
            with self.assertRaises(ValueError):
                reserve(self.root, self.p, action, "test", fingerprint_value, maximum, "test pricing")
        settle(self.root, "a", .3, "local-test")
        self.assertFalse(read_json(self.root / "costs.json")["entries"][0]["invoice_verified"])
        reserve(self.root, self.p, "b", "test", "input2", .6, "test pricing")

    def test_actual_cost_over_reservation_stops_new_calls(self):
        self.p["budget"] = {"cap": 1, "currency": "CNY", "authorization": "test only"}
        reserve(self.root, self.p, "a", "test", "input1", .3, "test pricing")
        settle(self.root, "a", .4, "test")
        with self.assertRaises(ValueError):
            reserve(self.root, self.p, "b", "test", "input2", .1, "test pricing")

    def test_zero_budget_cannot_call_paid_provider(self):
        with self.assertRaises(ValueError):
            reserve(self.root, self.p, "a", "test", "input", .1, "test pricing")

    def test_init_preserves_existing_project_and_clears_example(self):
        path = self.root / "new"
        init_project(path)
        self.assertEqual(read_json(path / "project.json")["shots"], [])
        self.assertFalse(validate(read_json(path / "project.json"), path)["ok"])
        with self.assertRaises(ValueError):
            init_project(path)

    def test_installer_is_idempotent_and_protects_local_edits(self):
        spec = importlib.util.spec_from_file_location("installer", ROOT / "scripts/install_skill.py")
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        path = self.root / "installed"
        self.assertEqual(installer.install(path)["status"], "installed")
        self.assertEqual(installer.install(path)["status"], "already_current")
        (path / "SKILL.md").write_text("local changes")
        with self.assertRaises(ValueError):
            installer.install(path, update=True)

    def test_installer_targets_claude_and_agents(self):
        spec = importlib.util.spec_from_file_location("installer", ROOT / "scripts/install_skill.py")
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        self.assertTrue(installer.TARGETS["claude"].startswith("~/.claude/skills/"))
        self.assertTrue(installer.TARGETS["codex"].startswith("~/.codex/skills/"))

    def test_authored_audio_is_audio_only_and_needs_basis(self):
        self.p["assets"]["music"]["origin"] = "authored_audio"
        self.assertTrue(self.check()["ok"])
        self.p["assets"]["music"].pop("rights_basis")
        self.assertTrue(any("authored_audio" in e for e in self.check()["errors"]))
        self.p["assets"]["photo"]["origin"] = "authored_audio"
        self.assertTrue(any("authored_audio" in e for e in self.check()["errors"]))

    def test_render_intermediates_are_lossless(self):
        args = encode_args(self.p["profile"])
        self.assertEqual(args[args.index("-qp") + 1], "0")
        self.assertNotIn("-crf", args)


class VoiceTests(unittest.TestCase):
    """Fake provider only: CI never sends text or money to a real TTS service."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.p = fixture()
        self.p["budget"] = {"cap": 1, "currency": "USD", "authorization": "test-only budget, fake provider"}
        self.calls = 0

    def tearDown(self):
        self.tmp.cleanup()

    def ok(self, host, path, body, timeout=120):
        self.calls += 1
        return {"data": {"audio": b"ID3fake".hex(), "status": 2}, "trace_id": "t1",
                "extra_info": {"usage_characters": 2 * len(body["text"]), "audio_length": 900},
                "base_resp": {"status_code": 0, "status_msg": "success"}}

    def run_tts(self, poster, items=None):
        return tts.synthesize(self.root, self.p, items or tts.narration_items(self.p), "voice-a",
                              price_per_10k_chars=1.0, pricing_basis="test price", poster=poster)

    def test_paid_lines_are_reserved_settled_and_cached(self):
        first = self.run_tts(self.ok)
        self.assertEqual(first["charged_lines"], 2)
        ledger = read_json(self.root / "costs.json")["entries"]
        self.assertTrue(all(e["status"] == "settled" and e["amount"] > 0 for e in ledger))
        again = self.run_tts(self.ok)
        self.assertEqual((again["charged_lines"], self.calls), (0, 2))
        self.assertTrue((self.root / "audio/narration/b1.mp3").is_file())

    def test_unknown_result_is_not_paid_twice(self):
        def drop(host, path, body, timeout=120):
            raise TimeoutError("connection dropped after send")
        with self.assertRaises(TimeoutError):
            self.run_tts(drop)
        self.assertEqual(read_json(self.root / "costs.json")["entries"][0]["status"], "reserved")
        with self.assertRaises(ValueError):
            self.run_tts(self.ok)
        self.assertEqual(self.calls, 0)

    def test_definite_provider_error_settles_at_zero(self):
        def reject(host, path, body, timeout=120):
            return {"base_resp": {"status_code": 1004, "status_msg": "auth failed"}}
        with self.assertRaises(ValueError):
            self.run_tts(reject)
        entry = read_json(self.root / "costs.json")["entries"][0]
        self.assertEqual((entry["status"], entry["amount"]), ("settled", 0))

    def test_price_evidence_and_budget_required(self):
        with self.assertRaises(ValueError):
            tts.synthesize(self.root, self.p, tts.narration_items(self.p), "voice-a", poster=self.ok)
        self.p["budget"] = {}
        with self.assertRaises(ValueError):
            self.run_tts(self.ok)
        self.assertEqual(self.calls, 0)

    def test_only_narration_goes_to_tts(self):
        self.p["beats"].append({"id": "q1", "original_quote": "Real speaker words.", "fact_ids": []})
        self.assertEqual([i for i, _ in tts.narration_items(self.p)], ["b1", "b2"])
        self.assertEqual([i for i, _ in tts.narration_items(self.p, ["b2"])], ["b2"])


class EncodeTests(unittest.TestCase):
    def test_actual_multisource_bilingual_score_render_and_audit(self):
        try:
            ffmpeg = binary("ffmpeg")
            binary("ffprobe")
        except ValueError as exc:
            if os.environ.get("REQUIRE_MEDIA_TESTS"):
                self.fail(str(exc))
            self.skipTest(str(exc))
        tmp = tempfile.TemporaryDirectory()
        if os.environ.get("VIDEO_TEST_OUTPUT"):
            root = Path(os.environ["VIDEO_TEST_OUTPUT"])
            root.mkdir(parents=True, exist_ok=True)
        else:
            root = Path(tmp.name)
        try:
            (root / "assets").mkdir(exist_ok=True)
            (root / "audio").mkdir(exist_ok=True)
            sources = [("wide", "testsrc2=size=640x360:rate=30"), ("portrait", "testsrc2=size=360x640:rate=30")]
            for aid, source in sources:
                run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", source, "-t", "5", "-an",
                     "-c:v", "libx264", "-threads", "2", "-pix_fmt", "yuv420p", "-y", root / f"assets/{aid}.mp4"])
            run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30",
                 "-frames:v", "1", "-threads", "1", "-y", root / "assets/photo.png"])
            for aid, hz in [("voice", 440), ("music", 220)]:
                run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", f"sine=frequency={hz}:sample_rate=48000:duration=5",
                     "-ac", "2", "-y", root / f"audio/{aid}.wav"])
            p = fixture()
            (root / "project.json").write_text(json.dumps(p, ensure_ascii=False))
            preflight = validate(p, root, "render", allow_test=True)
            self.assertTrue(preflight["ok"], preflight)
            result = mix(p, root, root / "audio/master.wav")
            self.assertEqual(result["listening_review"], "not_reviewed")
            output = root / "film-test.mp4"
            encoded = render(p, root, output)
            self.assertEqual(encoded["frames"], 117)
            self.assertEqual(frame_count(output), 117)
            report = audit(p, output, root / "qa.json")
            self.assertTrue(report["ok"], report["errors"])
            self.assertEqual(report["listening_review"], "not_reviewed")
            self.assertEqual(report["user_acceptance"], "not_assumed")
            frames = review_frames(p, output, root / "review")
            self.assertGreaterEqual(frames["frames"], 9)
            bridges = sorted((root / "work/render").glob("bridge-*.mp4"))
            self.assertEqual(len(bridges), 2)
            # Replacing the right source changes its bridge's cache key, even with same framing/timing.
            run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=c=blue:size=360x640:rate=30",
                 "-t", "5", "-c:v", "libx264", "-threads", "2", "-y", root / "assets/portrait.mp4"])
            render(p, root, root / "film-test-v2.mp4")
            self.assertEqual(len(list((root / "work/render").glob("bridge-*.mp4"))), 4)
            # A new local media file cannot claim more pixels than it actually contains.
            p["assets"]["portrait"]["quality"]["effective_width"] = 720
            self.assertFalse(validate(p, root, "render", allow_test=True)["ok"])
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
