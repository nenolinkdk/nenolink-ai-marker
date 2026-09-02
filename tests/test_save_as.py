from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from nenolink_ai_marker.app import MarkerApp


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
    processor.save.assert_called_once_with(processed,Path(chosen))
