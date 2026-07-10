"""WTForms-Formulardefinitionen für Eingabevalidierung.

Wir nutzen WTForms nur für die serverseitige Validierung (Validators, Fields).
CSRF wird durch das eigene Middleware-System in __init__.py verwaltet.
"""
import re
from datetime import datetime, date
from wtforms import Form, StringField, IntegerField, DateField, TimeField, SelectField
from wtforms.validators import DataRequired, Length, NumberRange, Regexp, ValidationError, Optional


HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')


def validate_hex_color(form, field):
    if field.data and not HEX_COLOR_RE.match(field.data):
        raise ValidationError(f'"{field.data}" ist keine gültige Hex-Farbe (z.B. #A1B2C3).')


class TrainingForm(Form):
    name = StringField(
        'Name',
        validators=[DataRequired(message='Name ist erforderlich.'), Length(max=100)]
    )
    category = SelectField(
        'Kategorie',
        choices=[
            ('training', 'Training'),
            ('game', 'Saison-Spiel'),
            ('event', 'Event'),
        ],
        validators=[Optional()],
    )
    weekday = IntegerField(
        'Wochentag',
        validators=[NumberRange(min=0, max=6, message='Ungültiger Wochentag (0–6).')]
    )
    start_date = DateField('Startdatum', validators=[DataRequired()])
    end_date = DateField('Enddatum', validators=[DataRequired()])
    start_time = TimeField('Startzeit', validators=[DataRequired()])

    def validate_end_date(self, field):
        if self.start_date.data and field.data and field.data < self.start_date.data:
            raise ValidationError('Enddatum darf nicht vor dem Startdatum liegen.')


class HiddenTrainingForm(Form):
    name = StringField(
        'Name',
        validators=[DataRequired(message='Name ist erforderlich.'), Length(max=100)]
    )
    category = SelectField(
        'Kategorie',
        choices=[
            ('training', 'Training'),
            ('game', 'Saison-Spiel'),
            ('event', 'Event'),
        ],
        validators=[Optional()],
    )
    date = DateField('Datum', validators=[DataRequired()])
    start_time = TimeField('Startzeit', validators=[DataRequired()])


class ActivityTypeForm(Form):
    label = StringField('Bezeichnung', validators=[DataRequired(), Length(max=100)])
    light_color = StringField('Hellmodus-Farbe', validators=[Optional(), validate_hex_color])
    dark_color = StringField('Dunkelmodus-Farbe', validators=[Optional(), validate_hex_color])


def validate_training_form(form_data):
    """Validiert ein Training-Formular und gibt (ok, errors) zurück."""
    form = TrainingForm(form_data)
    if form.validate():
        return True, {}
    return False, {field: errors for field, errors in form.errors.items()}


def validate_hidden_training_form(form_data):
    """Validiert ein einmaliges Training-Formular und gibt (ok, errors) zurück."""
    form = HiddenTrainingForm(form_data)
    if form.validate():
        return True, {}
    return False, {field: errors for field, errors in form.errors.items()}


def sanitize_color(color: str) -> str | None:
    """Gibt nur gültige Hexfarben zurück, sonst None."""
    if color and HEX_COLOR_RE.match(color.strip()):
        return color.strip()
    return None
