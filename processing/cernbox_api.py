from os import environ
from webdav3.client import Client
from pathlib import Path
from tqdm import tqdm

class CERNBoxAPI:
    def __init__(self):

        if "CERNBOX_HOST" not in environ or \
            "CERNBOX_LOGIN" not in environ or \
            "CERNBOX_PASSWORD" not in environ:
            raise KeyError("(Did you source setup.sh? See README for details on setting CERNBox credentials :D) In order to backup the files to the CERNBox you need to add the correct environment variables: \
                        CERNBOX_HOST, CERNBOX_LOGIN, CERNBOX_PASSWORD")
        self.options = {
            'webdav_hostname': environ["CERNBOX_HOST"],
            'webdav_login':    environ["CERNBOX_LOGIN"],
            'webdav_password': environ["CERNBOX_PASSWORD"]
        }
        self.client = Client(self.options)  
        self._base = Path("public")

    def make_remote_dir(self, directory: Path) -> Path:
        """
        Makes full paths in the CERNBox based off path

        For example if this path is not on the remote,
        my/remote/path/hey/yall/watch/this

        It will make the full path, so you do not have to build each part. 
        """
        # Handles case if user gives self._base at start of directory already :)
        if self._base.name != directory.parts[0]:
            remote_dir = self._base
        else:
            remote_dir = Path()

        for part in directory.parts:
            # slowly build the remote dir so it exists!
            remote_dir = remote_dir / part
            self.client.mkdir(str(remote_dir))
        return remote_dir
    
    def upload(self, local_path: Path, remote_dir: Path, overwrite=False) -> None:
        """
        Uploads all FILES in the local_path, local_path can also be a single file.
        Even upload_sync lets you upload directories, this gives extra constraint to upload with progress bar.
        Couldnt figure out how to do progress bar with their library :/

        local_path: Path to file or directory on local machine to upload to remote
        remote_dir: Directory on remote to upload file(s) to
        overwrite: if True it will overwrite all files in the directory instead of skipping them.
        """
        if not isinstance(remote_dir, Path):
            TypeError("remote_path must be a Path object")
        if not isinstance(local_path, Path):
            TypeError("local_path must be a Path object")
        if remote_dir.parts[0] == self._base.name:
            raise ValueError(f"Please do not include {self._base} in the directory. All files get put in {self._base} so I do it for you.")
        # create remote path
        if remote_dir.suffix:
            raise ValueError("Remote can only be a directory. This unfortunately constrains directories with periods in the name.")
        
        # Should create this dir now 
        remote_dir = self.make_remote_dir(remote_dir)
        if local_path.is_dir():
            # fetch and do the diff for speed?
            remote_files = self.fetch_remote(remote_dir)

            files_to_upload = [
                file_path for file_path in local_path.iterdir() if file_path.name not in remote_files
            ]
            if not files_to_upload:
                print("All synced up! No files to upload!")
                return
            
            prog_bar = tqdm(files_to_upload)
            for file in prog_bar:
                if not file.is_file():
                    continue
                prog_bar.set_description(f"Uploading {file.name}")
                self.client.upload_sync(
                    remote_path = str(remote_dir / file.name), 
                    local_path  = str(file),
                )
                
        elif local_path.is_file():
            self.client.upload_sync(
                remote_path = str(remote_dir / local_path.name), 
                local_path  = str(local_path),
            ) 
        else:
            raise ValueError(f"Your local path ({local_path}) is not a directory or file. Does it exist?")        

    def fetch_remote(self, remote_dir: Path) -> list:
        return self.client.list(str(remote_dir))
    