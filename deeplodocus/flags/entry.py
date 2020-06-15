from deeplodocus.utils import get_main_path
from deeplodocus.utils.flag import Flag
#
# ENTRIES
#

DEEP_ENTRY_INPUT = Flag(
    name="Model Input",
    description="Input entry",
    names=["input", "inputs", "inp", "x"]
)

DEEP_ENTRY_LABEL = Flag(
    name="Label",
    description="Label entry",
    names=["label", "labels", "lab", "target", "targets", "y_expected", "y_hat"]
)

DEEP_ENTRY_OUTPUT = Flag(
    name="Model Output",
    description="Output entry",
    names=["output", "outputs", "y"]
)

DEEP_ENTRY_ADDITIONAL_DATA = Flag(
    name="Additional data",
    description="Additional Data entry",
    names=["additional_data"]
)

DEEP_ENTRY_MODEL = Flag(
    name="Model",
    description="Model entry",
    names=["model", "network"]
)


DEEP_ENTRY_BASE_FILE_NAME = get_main_path() + "/data/auto-generated_dataset_source_folder_%i.dat"
