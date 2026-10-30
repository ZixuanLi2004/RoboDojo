from env.description_manager.layout_instruction import LayoutInstructionMixin
from env.environment.task_env import TaskEnv
from task.MobileArena.tasks.throw_away_trash import ThrowAwayTrashCommon


class ThrowAwayTrashLanguageCommon(LayoutInstructionMixin, ThrowAwayTrashCommon):
    pass


class throw_away_trash_l(ThrowAwayTrashLanguageCommon, TaskEnv):
    pass
