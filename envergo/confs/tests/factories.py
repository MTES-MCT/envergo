from factory.django import DjangoModelFactory

from envergo.confs.models import TopBar


class TopBarFactory(DjangoModelFactory):
    class Meta:
        model = TopBar

    message_md = "Message texte pour une **top bar**"
    is_active = True
