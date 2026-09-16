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


class InteractionCreateForm(forms.Form):
    occurred_at = forms.CharField(
        label="Occurred at",
        help_text=(
            "Enter an ISO date and time with an explicit UTC offset, for example "
            "2026-09-16T14:30:00-05:00."
        ),
    )
    body = forms.CharField(max_length=20000, strip=False, widget=forms.Textarea)
    participant_ids = forms.MultipleChoiceField(
        label="Participants", widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, *args, parties=(), selected_parties=(), **kwargs):
        super().__init__(*args, **kwargs)
        choices = {}
        for party in [*selected_parties, *parties]:
            choices[str(party.id)] = f"{party.display_name} ({party.kind})"
        self.fields["participant_ids"].choices = choices.items()


class InteractionForm(VersionForm, InteractionCreateForm):
    pass


class CommitmentCreateForm(forms.Form):
    description = forms.CharField(max_length=2000, strip=False, widget=forms.Textarea)
    owed_by_party_id = forms.ChoiceField(label="Owed by")
    owed_to_party_id = forms.ChoiceField(label="Owed to")
    due_on = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Due-date filters use the UTC calendar date.",
    )
    person_ids = forms.MultipleChoiceField(
        label="Linked people", widget=forms.CheckboxSelectMultiple
    )
    source_interaction_id = forms.ChoiceField(
        label="Source interaction", required=False
    )

    def __init__(
        self,
        *args,
        owed_by_parties=(),
        owed_to_parties=(),
        people=(),
        selected_people=(),
        interactions=(),
        selected_source=None,
        source_enabled=True,
        can_clear_hidden_source=False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        def party_choices(rows):
            return [
                (str(party.id), f"{party.display_name} ({party.kind})")
                for party in rows
            ]

        self.fields["owed_by_party_id"].choices = party_choices(owed_by_parties)
        self.fields["owed_to_party_id"].choices = party_choices(owed_to_parties)
        choices = {}
        for party in [*selected_people, *people]:
            choices[str(party.id)] = party.display_name
        self.fields["person_ids"].choices = choices.items()
        if source_enabled:
            source_choices = {"": "No source interaction"}
            if selected_source is not None:
                source_choices[str(selected_source.id)] = (
                    f"{selected_source.occurred_at}: {selected_source.body[:80]}"
                )
            for interaction in interactions:
                source_choices[str(interaction.id)] = (
                    f"{interaction.occurred_at}: {interaction.body[:80]}"
                )
            self.fields["source_interaction_id"].choices = source_choices.items()
        else:
            self.fields.pop("source_interaction_id")
            if can_clear_hidden_source:
                self.fields["clear_source_interaction"] = forms.BooleanField(
                    label="Clear the existing hidden source interaction", required=False
                )


class CommitmentForm(VersionForm, CommitmentCreateForm):
    pass
