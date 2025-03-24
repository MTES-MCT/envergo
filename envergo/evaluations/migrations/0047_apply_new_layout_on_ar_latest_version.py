import logging

from bs4 import BeautifulSoup
from django.db import migrations
from tqdm import tqdm

logger = logging.getLogger(__name__)

def apply_new_layout_on_ar_latest_versions(apps, schema_editor):
    Evaluation = apps.get_model("evaluations", "Evaluation")
    EvaluationVersion = apps.get_model("evaluations", "EvaluationVersion")
    qs = Evaluation.objects.all()
    total = qs.count()
    batch_size = 50
    i = 0
    with tqdm(total=total) as pbar:
        while i < total:
            evaluations = qs[i: i + batch_size].iterator()  # noqa
            to_update = []
            for evaluation in evaluations:
                latest_version = evaluation.versions.first()
                if not latest_version:
                    # no version, no need to rerender
                    continue

                html = BeautifulSoup(latest_version.content, "html.parser")
                new_layout_element = html.find("span", class_="regulation-result")
                if new_layout_element:
                    # this version already have new layout
                    # no need to rerender
                    continue

                for a_tag in html.find_all("a", class_="summary-link"):
                    spans = a_tag.find_all("span", recursive=False)

                    if len(spans) == 2:
                        regulation_label = spans[0]
                        nested_spans = spans[1].find_all("span", recursive=False)

                        if len(nested_spans) == 2:
                            probability = nested_spans[0]
                            action_link = nested_spans[1]

                            regulation_result = html.new_tag("span", **{"class": "regulation-result"})
                            regulation_result.append(regulation_label)
                            regulation_result.append(probability)

                            a_tag.clear()
                            a_tag.append(regulation_result)
                            a_tag.append(action_link)

                for parent in html.select("div.criteria button.fr-accordion__btn"):
                    spans = parent.find_all("span", recursive=False)

                    if len(spans) >= 2:
                        spans[0].extract()
                        spans[1].extract()
                        parent.insert(0, spans[1])  # Insert second span first
                        parent.insert(1, spans[0])  # Insert first span second

                latest_version.content = str(html)
                to_update.append(latest_version)

            EvaluationVersion.objects.bulk_update(to_update, ["content"])
            logger.info(f"{len(to_update)} evaluation versions updated")
            i += batch_size
            pbar.update(batch_size)


class Migration(migrations.Migration):
    dependencies = [
        ("evaluations", "0046_alter_evaluation_updated_at"),
    ]

    operations = [
        migrations.RunPython(
            apply_new_layout_on_ar_latest_versions, reverse_code=migrations.RunPython.noop
        )
    ]
