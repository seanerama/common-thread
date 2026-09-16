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


class RelationshipCreateForm(forms.Form):
    from_party_id = forms.ChoiceField(label="From party")
    to_party_id = forms.ChoiceField(label="To party")
    kind = forms.CharField(
        max_length=80,
        help_text="For example: employment, household_member, referral or other.",
    )
    role = forms.CharField(required=False)
    starts_on = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    ends_on = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

    def __init__(self, *args, from_parties=(), to_parties=(), **kwargs):
        super().__init__(*args, **kwargs)
        from_choices = [
            (str(party.id), f"{party.display_name} ({party.kind})")
            for party in from_parties
        ]
        to_choices = [
            (str(party.id), f"{party.display_name} ({party.kind})")
            for party in to_parties
        ]
        self.fields["from_party_id"].choices = from_choices
        self.fields["to_party_id"].choices = to_choices


class RelationshipForm(VersionForm):
    kind = forms.CharField(
        max_length=80,
        help_text="For example: employment, household_member, referral or other.",
    )
    role = forms.CharField(required=False)
    starts_on = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    ends_on = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )


class RelationshipCloseForm(VersionForm):
    ends_on = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
