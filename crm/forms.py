from django import forms


class VersionForm(forms.Form):
    expected_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)


class PersonForm(VersionForm):
    display_name = forms.CharField(label="Name", max_length=200)
    is_client = forms.BooleanField(label="Client", required=False)


class PartyCreateForm(forms.Form):
    display_name = forms.CharField(label="Name", max_length=200)
    is_client = forms.BooleanField(label="Client", required=False)


class PartyForm(VersionForm, PartyCreateForm):
    pass


class ContactPointForm(VersionForm):
    kind = forms.ChoiceField(choices=(("email", "Email"), ("phone", "Phone")))
    value = forms.CharField(max_length=320)
    label = forms.CharField(required=False)


class ContextNoteForm(VersionForm):
    body = forms.CharField(max_length=20000, strip=False, widget=forms.Textarea)
    source = forms.CharField(
        max_length=500,
        strip=False,
        help_text="Where did this context come from? Label any inference as your own.",
    )
