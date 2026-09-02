from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

from nenolink_ai_marker.badges import BadgeRepository, EXPECTED_STANDARD_BADGES
from nenolink_ai_marker.batch import BatchProcessor, RECOMMENDED_IMAGE_BYTES, RECOMMENDED_VIDEO_BYTES, destination_for, destination_root, find_ffmpeg, is_above_recommended_size, scan_folder
from nenolink_ai_marker.guide import open_user_guide
from nenolink_ai_marker.models import MarkerSettings
from nenolink_ai_marker.paths import docs_directory, localized_user_guide_path, user_guide_path


class ResourceAndBatchTests(unittest.TestCase):
    def test_scan_identifies_but_keeps_files_above_recommended_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); image=root/"large.jpg"; video=root/"large.mp4"
            with image.open("wb") as stream:stream.truncate(RECOMMENDED_IMAGE_BYTES+1)
            with video.open("wb") as stream:stream.truncate(RECOMMENDED_VIDEO_BYTES+1)
            scan=scan_folder(root)
            self.assertEqual(len(scan.oversized),2)
            self.assertIn(image,scan.images); self.assertIn(video,scan.videos)
            self.assertTrue(is_above_recommended_size(image)); self.assertTrue(is_above_recommended_size(video))
    def test_exact_standard_badge_set_and_metadata(self):
        root=Path(__file__).resolve().parents[1]/"assets"/"badges"
        repo=BadgeRepository(root)
        self.assertEqual(set(p.name for p in repo.list_badges()),set(EXPECTED_STANDARD_BADGES))
        self.assertEqual(len(repo.list_badges()),10)
        for name in EXPECTED_STANDARD_BADGES:
            self.assertIsNotNone(repo.metadata(name))
            with Image.open(root/name) as image:self.assertEqual(image.mode,"RGBA")

    def test_docs_paths_source_and_packaged(self):
        module=Path("C:/project/nenolink_ai_marker/paths.py")
        self.assertEqual(docs_directory(frozen=False,module_file=module),Path("C:/project/docs"))
        exe=Path("C:/Apps/Nenolink-AI-Marker/Nenolink-AI-Marker.exe")
        self.assertEqual(user_guide_path(frozen=True,executable=exe),Path("C:/Apps/Nenolink-AI-Marker/docs/Nenolink-AI-Marker-User-Guide-EN.pdf"))

    def test_localized_guide_paths_and_english_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); docs=root/"docs"; docs.mkdir()
            english=docs/"Nenolink-AI-Marker-User-Guide-EN.pdf"; danish=docs/"Nenolink-AI-Marker-User-Guide-DA.pdf"
            english.touch(); danish.touch(); executable=root/"Nenolink-AI-Marker.exe"
            self.assertEqual(localized_user_guide_path("da",frozen=True,executable=executable),danish)
            self.assertEqual(localized_user_guide_path("en",frozen=True,executable=executable),english)
            self.assertEqual(localized_user_guide_path("fr",frozen=True,executable=executable),english)

    def test_missing_all_guides_returns_english_path_for_graceful_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/"docs").mkdir(); executable=root/"Nenolink-AI-Marker.exe"
            self.assertEqual(localized_user_guide_path("da",frozen=True,executable=executable),root/"docs"/"Nenolink-AI-Marker-User-Guide-EN.pdf")

    def test_missing_user_guide(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):open_user_guide(Path(folder)/"missing.pdf")

    def test_folder_scanning_and_recursive_scanning(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/"a.jpg").touch(); (root/"b.mp4").touch(); (root/"note.txt").touch(); (root/"sub").mkdir(); (root/"sub"/"c.png").touch()
            flat=scan_folder(root); recursive=scan_folder(root,True)
            self.assertEqual((len(flat.images),len(flat.videos),len(flat.unsupported)),(1,1,1))
            self.assertEqual(len(recursive.images),2)

    def test_output_roots_structure_and_naming(self):
        root=Path("C:/input"); source=root/"nested"/"photo.jpg"
        settings=MarkerSettings(output_subfolder="AI-marked")
        self.assertEqual(destination_root(settings,root),root/"AI-marked")
        self.assertEqual(destination_for(source,root,Path("D:/out"),True),Path("D:/out/nested/photo_ai.jpg"))
        self.assertEqual(destination_for(source,root,Path("D:/out"),True,"_marked"),Path("D:/out/nested/photo_marked.jpg"))
        video=root/"nested"/"interview.mov"
        self.assertEqual(destination_for(video,root,Path("D:/out"),True),Path("D:/out/nested/interview_ai.mov"))
        settings.output_preference="separate"; settings.output_folder="D:/chosen"
        self.assertEqual(destination_root(settings,root),Path("D:/chosen"))

    def test_skip_processed_and_error_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder); root=base/"input"; root.mkdir(); good=root/"good.png"; corrupt=root/"bad.png"; done=root/"done_ai.png"; badge=base/"badge.png"
            Image.new("RGB",(20,20),"white").save(good); corrupt.write_text("bad"); Image.new("RGB",(20,20),"white").save(done); Image.new("RGBA",(10,4),"red").save(badge)
            scan=scan_folder(root); settings=MarkerSettings(output_subfolder="out",skip_processed=True)
            result=BatchProcessor().process(scan,badge,settings)
            self.assertEqual(result.successful,1); self.assertEqual(result.skipped,1); self.assertEqual(len(result.errors),1)
            self.assertTrue((root/"out"/"good_ai.png").is_file())

    def test_batch_custom_suffix_keeps_source_and_names_output(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder); root=base/"input"; root.mkdir(); source=root/"photo.jpg"; badge=base/"badge.png"
            Image.new("RGB",(20,20),"white").save(source); original=source.read_bytes(); Image.new("RGBA",(10,4),"red").save(badge)
            result=BatchProcessor().process(scan_folder(root),badge,MarkerSettings(output_subfolder="out",batch_filename_suffix="_published"))
            self.assertEqual(result.successful,1)
            self.assertTrue((root/"out"/"photo_published.jpg").is_file())
            self.assertEqual(source.read_bytes(),original)

    def test_missing_ffmpeg(self):
        with patch("nenolink_ai_marker.batch.Path.is_file",return_value=False), patch("shutil.which",return_value=None):self.assertIsNone(find_ffmpeg())

    def test_application_local_ffmpeg_is_preferred(self):
        found=find_ffmpeg()
        self.assertIsNotNone(found)
        self.assertTrue(str(found).endswith("tools\\ffmpeg\\ffmpeg.exe"))

    def test_video_processing_maps_filtered_video_and_loops_badge(self):
        completed=type("Completed",(),{"returncode":0,"stderr":""})()
        with patch("nenolink_ai_marker.batch.shutil.which",return_value="C:/ffmpeg.exe"), patch("nenolink_ai_marker.batch.subprocess.run",return_value=completed) as run:
            BatchProcessor.process_video(Path("input.mp4"),Path("badge.png"),Path("output.mp4"),MarkerSettings())
        command=run.call_args.args[0]
        self.assertIn("-loop",command); self.assertIn("[outv]",command)
        self.assertEqual(command[command.index("-map")+1],"[outv]")
        self.assertIn("shortest=1",command[command.index("-filter_complex")+1])


if __name__=="__main__":unittest.main()
