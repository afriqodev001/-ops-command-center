from django import forms


class RunPromptForm(forms.Form):
    prompt = forms.CharField(required=True)
    user_key = forms.CharField(required=False, initial="localuser")
    clear_attachments = forms.BooleanField(required=False, initial=True)


class BatchRunForm(forms.Form):
    batch_text = forms.CharField(required=True, widget=forms.Textarea)
    name = forms.CharField(required=False)
    user_key = forms.CharField(required=False, initial="localuser")
