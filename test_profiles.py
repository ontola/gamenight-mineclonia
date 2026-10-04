import base64
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from profiles import avatar, appearances, face_pixels, png, publish, rgb, skin_pixels


def sample_players(count=4):
    result=[]
    for i,(name,color,skin) in enumerate(zip(('Alex','Bo','Cléo','Dev'),
            ('#4daf7c','#e36c76','#648cdd','#d7ad43'),('#f5e9be','#905c40','#bf855b','#efc39a'))):
        px=[None]*2304
        def rect(x,y,w,h,c):
            for row in range(y,y+h):
                for col in range(x,x+w): px[row*48+col]=c
        rect(12,14,24,8,('#43352b','#7d4bd1','#d27732','#2d638d')[i])
        rect(18,10-i,12,6+i,('#43352b','#7d4bd1','#d27732','#2d638d')[i])
        for x in (20,29):
            rect(x,25,4,4,'#ffffff');rect(x+2,26,2,3,'#1a1a1a')
        rect(23,33,9,2,'#1a1a1a')
        if i%2: rect(25,35,5,1,'#1a1a1a')
        result.append(dict(id=f'test-player-{i}',name=name,color=color,skin_color=skin,
            avatar=json.dumps(dict(v=1,w=48,h=48,px=px))))
    return result[:count]


def seats(indices): return [dict(index=i,occupant=dict(kind='local',player_id=f'test-player-{i}')) for i in indices]


class Profiles(unittest.TestCase):
    def test_decoder_v1_and_legacy_transparency(self):
        p=json.dumps(dict(v=1,w=2,h=1,px=['#0f172a',None]))
        self.assertEqual(avatar(p),(2,1,[(15,23,42),None]))
        self.assertEqual(avatar('["#0F172A","#ff0000","bad","00ff00"]'),(2,2,[None,(255,0,0),None,(0,255,0)]))
        for bad in ('null','{}','[]','[null]','["red","blue"]',json.dumps(dict(v=1,w=257,h=1,px=[])),
                json.dumps(dict(v=1,w=True,h=1,px=['#ffffff'])),json.dumps(dict(v=2,w=1,h=1,px=['#ffffff']))):
            self.assertIsNone(avatar(bad))
        self.assertIsNone(rgb('#fff:^[texture'))

    def test_head_anchors_match_protocol(self):
        skin=(1,2,3)
        for size,xy in ((16,(2,5)),(32,(10,13)),(48,(24,28))):
            cells=[None]*(size*size);cells[xy[1]*size+xy[0]]='#abcdef'
            face=face_pixels(json.dumps(dict(v=1,w=size,h=size,px=cells)),skin)
            self.assertEqual(face[28*48+24],(171,205,239))

    def test_sparse_seats_use_player_ids_not_array_order(self):
        players=sample_players()
        result=appearances(seats([3,1]),list(reversed(players)))
        self.assertEqual(set(result),{'Couch2','Couch4'})
        self.assertEqual(result['Couch4']['name'],'Dev')
        self.assertEqual(result['Couch2']['color'],'#e36c76')
        self.assertNotEqual(result['Couch2']['skin'],result['Couch4']['skin'])

    def test_untrusted_names_colors_and_missing_profiles(self):
        players=[dict(id='test-player-0',name='Éva\x1b\n\u202e',color='red^[combine:',avatar='bad')]
        p=appearances(seats([0,3]),players)
        self.assertEqual(p['Couch1']['name'],'Éva')
        self.assertEqual(p['Couch1']['color'],'#4daf7c')
        self.assertEqual(p['Couch4']['name'],'Player 4')
        self.assertLess(len(p['Couch1']['skin']),65536)
        players[0]['name']='a'*100
        self.assertEqual(len(appearances(seats([0]),players)['Couch1']['name']),32)

    def test_png_and_skin_uv_keep_armor_transparent(self):
        face=face_pixels(None,(1,2,3));pixels=skin_pixels(face,(1,2,3),(4,5,6))
        self.assertEqual(pixels[25*6*384+20*6],(4,5,6))
        self.assertEqual(pixels[28*6*384+42*6],(1,2,3))
        self.assertIsNone(pixels[10*6*384+42*6])
        image=png(2,1,[(1,2,3),None]);offset=8;raw=b''
        while offset<len(image):
            n=struct.unpack('>I',image[offset:offset+4])[0];kind=image[offset+4:offset+8];data=image[offset+8:offset+8+n]
            self.assertEqual(zlib.crc32(kind+data),struct.unpack('>I',image[offset+8+n:offset+12+n])[0])
            if kind==b'IDAT': raw+=data
            offset+=12+n
        self.assertEqual(zlib.decompress(raw),b'\0\1\2\3\xff\0\0\0\0')

    def test_publish_updates_and_clears_old_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);players=sample_players(1)
            publish(root,seats([0]),players);p=root/'world/gamenight/profiles.json';mtime=p.stat().st_mtime_ns
            publish(root,seats([0]),players);self.assertEqual(p.stat().st_mtime_ns,mtime)
            publish(root,seats([0]),[]);self.assertEqual(json.loads(p.read_text())['Couch1']['name'],'Player 1')
            publish(root,[],[]);self.assertEqual(json.loads(p.read_text()),{})
