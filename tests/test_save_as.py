from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from nenolink_ai_marker.app import MarkerApp
from nenolink_ai_marker.metadata import marker_metadata


def test_single_file_save_as_suggests_ai_name_and_uses_edited_filename(tmp_path):
    source=tmp_path/"photo.jpg"; source.touch(); (tmp_path/"photo_ai.jpg").touch(); badge=tmp_path/"badge.png"
    processor=Mock(); processed=object(); processor.process.return_value=processed
    app=SimpleNamespace(
        badges=SimpleNamespace(find=lambda _:badge), badge_var=SimpleNamespace(get=lambda:"ai-assisted.png"),
        sources=[source], translator=SimpleNamespace(text=lambda key,**values:key), processor=processor,
        settings=Mock(return_value=object()), status_var=Mock(),
    )
    chosen=tmp_path/"photo_test.jpg"

    with patch("nenolink_ai_marker.app.filedialog.asksaveasfilename",return_value=str(chosen)) as dialog, patch("nenolink_ai_marker.app.messagebox.showinfo"):
        MarkerApp.save_images(app)

    assert dialog.call_args.kwargs["initialfile"]=="photo_ai.jpg"
    assert dialog.call_args.kwargs["initialdir"]==str(tmp_path)
    assert dialog.call_args.kwargs["defaultextension"]==".jpg"
    assert dialog.call_args.kwargs["confirmoverwrite"] is True
    processor.save.assert_called_once_with(processed,Path(chosen),marker_metadata("ai-assisted.png"))


def test_single_video_save_as_preserves_extension_and_uses_edited_name(tmp_path):
    source=tmp_path/"testvideo.mp4"; source.write_bytes(b"original-video"); (tmp_path/"testvideo_ai.mp4").touch(); badge=tmp_path/"badge.png"
    batch_processor=Mock()
    status_var=Mock()
    settings=object()
    app=SimpleNamespace(
        badges=SimpleNamespace(find=lambda _:badge), badge_var=SimpleNamespace(get=lambda:"ai-video.png"),
        sources=[source], translator=SimpleNamespace(text=lambda key,**values:(f"Video saved successfully: {values['name']}" if key=="video.saved_name" else key)),
        processor=Mock(), batch_processor=batch_processor, settings=Mock(return_value=settings), status_var=status_var,
    )
    chosen=tmp_path/"testvideo_demo.mov"

    with patch("nenolink_ai_marker.app.filedialog.asksaveasfilename",return_value=str(chosen)) as dialog, patch("nenolink_ai_marker.app.messagebox.showinfo"):
        MarkerApp.save_images(app)

    assert dialog.call_args.kwargs["initialfile"]=="testvideo_ai.mp4"
    assert dialog.call_args.kwargs["defaultextension"]==".mp4"
    assert dialog.call_args.kwargs["confirmoverwrite"] is True
    batch_processor.process_video.assert_called_once_with(source,badge,Path(chosen),settings,marker_metadata("ai-video.png"))
    status_var.set.assert_called_once_with("Video saved successfully: testvideo_demo.mov")
    assert source.read_bytes()==b"original-video"
