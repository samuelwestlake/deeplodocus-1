#
# DEEP FILTER OUT OF BOUND COMMANDS
#
DEEP_FILTER = ["wake()"]
DEEP_FILTER_ENDS_WITH = []
# DEEP_FILTER_INCLUDES = ["__", "config.save", "._"]
DEEP_FILTER_INCLUDES = ["config.save"]
DEEP_FILTER_STARTS_WITH = ["_"]
DEEP_FILTER_STARTS_ENDS_WITH = []


#
# DEEP FILTER OUT OF CONFIG ENTRIES
#

DEEP_FILTER_OPTIMIZERS = ["optimizer", "optimizers"]