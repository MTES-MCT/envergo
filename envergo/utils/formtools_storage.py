from django.core.files.uploadedfile import UploadedFile
from formtools.wizard.storage.exceptions import NoFileStorageConfigured
from formtools.wizard.storage.session import SessionStorage


class MultiFileSessionStorage(SessionStorage):
    """Custom formtools storage to handle multiple file uploads.

    The `formtools` extension provides a wizard view that is used to split
    forms into several steps.

    The WizardView subclass uses a Storage utility class to store data between
    steps. Unfortunately, this class does not handle the case
    when multiple files are uploaded for a single input[type=file] field with
    `multiple=true`.

    See https://github.com/jazzband/django-formtools/issues/98

    This class is a tweaked version to handle such a use case.

    Note: somehow, it really ressembles the solution existing here:
    https://github.com/astahlhofen/formtools-wizard-multiple-fileupload

    """

    def set_step_files(self, step, files):
        if files and not self.file_storage:
            raise NoFileStorageConfigured(
                "You need to define 'file_storage' in your "
                "wizard view in order to handle file uploads."
            )

        if step not in self.data[self.step_files_key]:
            self.data[self.step_files_key][step] = {}

        if not files:
            return

        for field in files.keys():
            field_files = files.getlist(field)
            file_dicts = []
            for field_file in field_files:
                tmp_filename = self.file_storage.save(field_file.name, field_file)
                file_dict = {
                    "tmp_name": tmp_filename,
                    "name": field_file.name,
                    "content_type": field_file.content_type,
                    "size": field_file.size,
                    "charset": field_file.charset,
                }
                file_dicts.append(file_dict)

            self.data[self.step_files_key][step][field] = file_dicts

    def get_step_files(self, step):
        wizard_files = self.data[self.step_files_key].get(step, {})

        if wizard_files and not self.file_storage:
            raise NoFileStorageConfigured(
                "You need to define 'file_storage' in your "
                "wizard view in order to handle file uploads."
            )

        files = {}
        for field, field_files in wizard_files.items():
            files[field] = []

            for field_dict in field_files:
                field_dict = field_dict.copy()
                tmp_name = field_dict.pop("tmp_name")
                if (step, field) not in self._files:
                    self._files[(step, field)] = UploadedFile(
                        file=self.file_storage.open(tmp_name), **field_dict
                    )

                files[field] = self._files[(step, field)]
        return files or None

    def reset(self):
        # Store unused temporary file names in order to delete them
        # at the end of the response cycle through a callback attached in
        # `update_response`.
        wizard_files = self.data[self.step_files_key]
        for step_files in wizard_files.values():
            for step_field_files in step_files.values():
                for step_file in step_field_files:
                    self._tmp_files.append(step_file["tmp_name"])
        self.init_data()
