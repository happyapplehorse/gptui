import pytest

from gptui.controllers.tube_files_control import TubeFiles
from gptui.utils.my_text import MyText as Text

class TestTubeFiles:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):

        class Displayer:
            def update(self, content):
                self.display = content
        
        self.displayer = Displayer()
        self.file_path = tmp_path / "files_test_data"
        self.file_path.mkdir(exist_ok=True)

    @pytest.mark.asyncio
    async def test_write_read_file_async(self):
        tf = TubeFiles(self.displayer)
        file_content = "This is a test."
        file_path = self.file_path / "test.txt"
        await tf.write_file_async(file_path, file_content)
        content = await tf.read_file_async(file_path)
        assert content == "This is a test."
        content = await tf.read_file_async(self.file_path / "test1.txt")
        assert content is None
        assert self.displayer.display == Text("File or directory not found", "yellow")
