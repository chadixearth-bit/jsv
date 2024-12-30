from django import template

register = template.Library()

@register.filter(name='addclass')
def addclass(field, css):
    """Add CSS classes to form field"""
    return field.as_widget(attrs={"class": css})
