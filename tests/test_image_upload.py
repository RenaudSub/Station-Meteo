"""Upload validation, storage boundaries and HTTP permissions."""
import base64
from io import BytesIO
import json
from types import SimpleNamespace
from pathlib import Path
import pytest
from PIL import Image
from homeassistant.core import HomeAssistant
from custom_components.station_meteo.image_upload import ImageUploadView, save_image, MAX_IMAGE_BYTES


def image_content(fmt):
    stream=BytesIO()
    Image.new('RGB',(20,10),'blue').save(stream,format=fmt)
    return base64.b64encode(stream.getvalue()).decode()


def test_supported_files_unique_names_and_corrupt_data(tmp_path):
    directory=tmp_path/'station_meteo'/'images'
    for fmt,extension in [('JPEG','jpg'),('PNG','png'),('WEBP','webp'),('GIF','gif')]:
        encoded=image_content(fmt)
        url=save_image(directory,encoded)
        assert url.startswith('/station_meteo/images/') and url.endswith('.'+extension)
        assert (directory/Path(url).name).read_bytes()==base64.b64decode(encoded)
        assert save_image(directory,encoded)!=url
    for data in [None,'$$$',base64.b64encode(b'<html>fake.jpg</html>').decode(),'A'*(((MAX_IMAGE_BYTES+2)//3)*4+4)]:
        with pytest.raises(ValueError):save_image(directory,data)
    assert len(list(directory.iterdir()))==8


@pytest.mark.asyncio
async def test_view_auth_and_upload_does_not_apply_settings(tmp_path):
    hass=HomeAssistant(str(tmp_path))
    hass.data['station_meteo']={'loaded':True,'config':{'background_url':''}}
    directory=tmp_path/'station_meteo'/'images'
    view=ImageUploadView(hass,directory)
    class Request(dict):
        async def json(self):return {'filename':'../../evil.jpg','content':image_content('JPEG')}
    try:
        response=await view.post(Request())
        assert response.status==403
        response=await view.post(Request(hass_user=SimpleNamespace(is_admin=False)))
        assert response.status==403
        assert not directory.exists()
        response=await view.post(Request(hass_user=SimpleNamespace(is_admin=True)))
        assert response.status==200
        url=json.loads(response.body)['url']
        assert (directory/Path(url).name).exists()
        assert hass.data['station_meteo']['config']['background_url']==''
        assert not (tmp_path/'evil.jpg').exists()
        hass.data['station_meteo']['loaded']=False
        response=await view.post(Request(hass_user=SimpleNamespace(is_admin=True)))
        assert response.status==503
    finally:
        await hass.async_stop(force=True)


def test_animated_transparent_images_preserve_all_bytes_and_frames(tmp_path):
    for fmt in ('GIF', 'WEBP'):
        stream = BytesIO()
        frames = [Image.new('RGBA', (24, 24), color) for color in ((0,0,0,0),(50,60,70,255))]
        frames[0].save(stream, format=fmt, save_all=True, append_images=frames[1:], duration=100, loop=0)
        original = stream.getvalue()
        url = save_image(tmp_path, base64.b64encode(original).decode())
        saved = tmp_path / Path(url).name
        assert saved.read_bytes() == original
        with Image.open(saved) as image:
            assert image.n_frames == 2
            assert image.convert('RGBA').getextrema()[3][0] == 0


def test_svg_arrows_are_preserved_and_active_content_rejected(tmp_path):
    assets=Path(__file__).parents[1]/'custom_components/station_meteo/frontend/compass-assets'
    for filename in ('arrow-feathers.svg','arrow-modern.svg'):
        data=(assets/filename).read_bytes()
        url=save_image(tmp_path,base64.b64encode(data).decode(),'arrow')
        assert url.endswith('.svg')
        assert (tmp_path/Path(url).name).read_bytes()==data
        with pytest.raises(ValueError):save_image(tmp_path,base64.b64encode(data).decode())
    prefix='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 320">'
    bad=[prefix+'<script>alert(1)</script></svg>',prefix+'<path onload="x"/></svg>',prefix+'<image href="https://example.com/x"/></svg>',prefix+'<path fill="url(https://example.com/x)"/></svg>',prefix+'<foreignObject/></svg>','<!DOCTYPE svg [<!ENTITY x "x">]>'+prefix+'</svg>']
    for svg in bad:
        with pytest.raises(ValueError):save_image(tmp_path,base64.b64encode(svg.encode()).decode(),'arrow')
