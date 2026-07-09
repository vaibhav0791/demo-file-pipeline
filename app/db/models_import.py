# Import ALL models here (and only here) so metadata.create_all can see them
from app.models.record import Record  # noqa: F401
from app.models.fetch_run import FetchRun  # noqa: F401
from app.models.master_target import MasterTarget  # noqa: F401