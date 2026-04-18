from copilot_chat.models import PromptPack


def load_all_packs():
    return list(PromptPack.objects.filter(enabled=True).order_by('name'))
