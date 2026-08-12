from django import forms


class DateRangeReportForm(forms.Form):
    """Shared filter bar for all report pages."""
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        if date_from and date_to and date_from > date_to:
            self.add_error('date_to', "End date cannot be before start date.")
        return cleaned_data


class SalesReportForm(DateRangeReportForm):
    granularity = forms.ChoiceField(
        required=False,
        choices=(('day', 'Daily'), ('week', 'Weekly'), ('month', 'Monthly')),
        initial='day',
    )
    include_cancelled = forms.BooleanField(required=False, initial=False)


class PaymentReportForm(DateRangeReportForm):
    granularity = forms.ChoiceField(
        required=False,
        choices=(('day', 'Daily'), ('week', 'Weekly'), ('month', 'Monthly')),
        initial='day',
    )


class OutstandingReportForm(DateRangeReportForm):
    only_overdue = forms.BooleanField(required=False, initial=False)




