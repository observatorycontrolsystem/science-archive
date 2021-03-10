from rest_framework.serializers import ValidationError


class ZipValidator():
    def __call__(self, attrs):
        selected_frames_count = len(attrs.get('frame_ids', []))
        uncompress = attrs.get('uncompress', False)
        if uncompress == True and selected_frames_count > 10:
            raise ValidationError('A maximum of 10 frames can be downloaded with the uncompress flag. Please '
                                  'try again with fewer frame_ids.')
