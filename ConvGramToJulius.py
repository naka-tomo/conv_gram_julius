# encoding: utf8
import codecs
import os
import sys
import re

slotIdFinder = re.compile( "\$slot[A-z0-9-]*" )

def ToHiragana( str ):
    hiragana = str
    return hiragana

def ToOnso( str ):
    kana = ToHiragana( str )
    for n in(3,2,1):
        for k,o in kana2hiragana.items():
            if len(k)==n:   # 長いものから変換
                kana = kana.replace( k , o )

    kana = kana.replace(" :" , ":" )
    kana = kana.replace("o u" , "o:")
    return kana

def Normalize( str ):
    # 不要な文字を取り除く
    str = str.replace( "\n" , "" )
    str = str.replace( "\r" , "" )

    # slotidの両端にスペースを入れる
    for slotId in slotIdFinder.findall( str ):
        str = str.replace( slotId , " " + slotId + " " )

    # 句読点は全て半角スペースにする
    str = str.replace( u"　" , " " )

    # 句読点は全て全角にしてう白いスペースを入れる
    str = str.replace( u"，" , u"、 " )
    str = str.replace( u"、" , u"、 " )
    str = str.replace( u"。" , u"。 " )
    str = str.replace( u"．" , u"。 " )
    str = str.replace( "," , u"、 " )
    str = str.replace( "." , u"。 " )
    str = str.replace( "\t" , " " )

    while "  " in str:
        str = str.replace( "  " , " " )

    return str

def Gram2ID( id , words , idDict ):
    beginID = "B_" + id
    endID = "E_" + id
    idGram = [beginID]

    for w in words:
        if w[0]=="$":
            # $slot_**の場合は$を覗いて登録
            idGram.append(w[1:])
        else:
            if w in idDict:
                # 既に辞書に入っていればそのidを使う
                idGram.append( idDict[w][0] )
            else:
                # 辞書になければ新たに生成
                id = "word%03d" % (len(idDict))
                onso = ToOnso( w )
                idDict[w] = (id, onso)
                idGram.append(id)

    idGram.append(endID)
    return idGram

def LoadGram( filename ):
    lines = codecs.open( filename , "r" , "sjis" ).readlines()
    lines = [ l for l in lines ]

    # grammars : [ (定型文id, 単語のリスト, 単語idのリスト), ... ]
    # slots : { 単語クラス : (単語ID, 単語文字列, 音素列), ... }
    # idDict : { 単語文字列 : (単語ID, 音素表記) }
    # utterance : [ (発話id, 文章), ... ]
    grammars = []
    slots = {}
    #idDict = { "<s>" : ("NS_B","silB") , "</s>" : ("NS_E","silE") }
    idDict = {}
    utterances = []

    # [GRAMMAR]を読み込み
    start = False
    for line in lines:
        # 文法セクションの開始
        if "[GRAMMAR]" in line:
            start = True
            continue

        if start:
            # 文法セクションの修了
            if "[" in line:
                break

            if ":" in line:
                id,gram = line.split(":")
                id = id.strip()
                words = Normalize(gram).strip().split()
                gramID = Gram2ID( id , words , idDict )
                grammars.append( [id,words,gramID] )
                print( id,gram," ".join(gramID) )

    # [NOUN]を読み込み
    start = False
    classID = ""
    for line in lines:
        # 文法セクションの開始
        if "[NOUN]" in line:
            start = True
            continue

        if start:
            # 文法セクションの修了
            if "[" in line:
                break
            elif "$" in line:
                classID = line.strip()[1:]
                slots[classID] = []

            if ":" in line:
                id,slot = line.split(":")
                id = id.strip()
                slot = Normalize(slot).strip()
                onso = ToOnso(slot)
                slots[classID].append( [id,slot,onso] )
                print( classID ,id, slot, onso )



    return grammars,slots,idDict

def SaveJuliusGram( grammars , slots, idDict, basename ):

    slotClassUsedInGram = []
    f = codecs.open( basename + ".grammar" , "w" , "sjis" )
    for g in grammars:
        f.write( "S : " + " ".join(g[2]) + "\n" )
        for w in g[2]:
            if w.find("slot_")==0:
                slotClassUsedInGram.append( w )
    f.close()

    f = codecs.open( basename + ".voca" , "w" , "sjis" )
    for slotClass in slots.keys():
        if not slotClass in slotClassUsedInGram:
            continue

        f.write("%" + slotClass + "\n" )
        for slotInfo in slots[slotClass]:
            f.write( slotInfo[1] + "\t" + slotInfo[2] + "\n" )
        f.write("\n")

    for w in idDict.keys():
        f.write( "%" + idDict[w][0] + "\n" )
        f.write( w + "\t" + idDict[w][1] + "\n\n" )

    # 文章の開始と終端に定型文IDを埋め込む
    for g in grammars:
        f.write( "%B_" + g[0] + "\n")
        f.write( "<s>\tsilB\n\n" )
        f.write( "%E_" + g[0] + "\n")
        f.write( "</s>\tsilE\n\n" )
    f.close()


word2slotID = {}
classID2Name = {}
def CompileGrammar( txtgram, juliusgram ):
    global word2slotID
    global classID2Name

    word2slotID = {}
    classID2Name = {}


    grammars,slots,idDict = LoadGram(txtgram)
    SaveJuliusGram( grammars , slots, idDict, juliusgram )


    success = True
    p = os.popen( ".\\perl\\perl.exe mkdfa.pl " + juliusgram, "r" )
    for line in p:
        print(line)
        if "no .dfa or .dict file generated" in line:
            success = False
            print("error")
    p.close()

    classID2Name = {}
    for line in open(juliusgram+".term","r"):
        line = line.replace("\n", "")
        line = line.split("\t")
        classid = line[0]
        className = line[1]
        classID2Name[classid] = className

    word2slotID = {}
    for className in slots.keys():
        for slotInfo in slots[className]:
            word2slotID[(className,slotInfo[1])] = slotInfo[0]
            print(className+"."+slotInfo[1])

    print(word2slotID)
    print(classID2Name)

    return success

def GetGramID( classIDs ):
    if len(classIDs)!=0:
        if classIDs[0] in classID2Name:
            className = classID2Name[ classIDs[0] ]
            return className.replace("B_" , "" )
    return ""

def GetSlotID( classIDs, words ):
    slotIDs = []
    slotStrs = []
    for cid,w in zip(classIDs,words):
        if cid in classID2Name:
            className = classID2Name[cid]
            if className.find("slot_")==0:
                if (className,w) in word2slotID:
                    slotid = word2slotID[(className,w)]
                    slotIDs.append(slotid)
                    slotStrs.append(w)
        else:
            print( cid,"が辞書にない" )
            return [],[]

    return( slotIDs, slotStrs )


def main():

    print( CompileGrammar( sys.argv[1], sys.argv[2] ) )





kana2hiragana = {
u"う゛ぁ" : "b a ",
u"う゛ぃ" : "b i ",
u"う゛ぇ" : "b e ",
u"う゛ぉ" : "b o ",
u"う゛ゅ" : "by u ",
u"ぅ゛" : "b u ",
u"あぁ" : "a a ",
u"いぃ" : "i i ",
u"いぇ" : "i e ",
u"いゃ" : "y a ",
u"うぅ" : "u: ",
u"えぇ" : "e e ",
u"おぉ" : "o: ",
u"かぁ" : "k a: ",
u"きぃ" : "k i: ",
u"くぅ" : "k u: ",
u"くゃ" : "ky a ",
u"くゅ" : "ky u ",
u"くょ" : "ky o ",
u"けぇ" : "k e: ",
u"こぉ" : "k o: ",
u"がぁ" : "g a: ",
u"ぎぃ" : "g i: ",
u"ぐぅ" : "g u: ",
u"ぐゃ" : "gy a ",
u"ぐゅ" : "gy u ",
u"ぐょ" : "gy o ",
u"げぇ" : "g e: ",
u"ごぉ" : "g o: ",
u"さぁ" : "s a: ",
u"しぃ" : "sh i: ",
u"すぅ" : "s u: ",
u"すゃ" : "sh a ",
u"すゅ" : "sh u ",
u"すょ" : "sh o ",
u"せぇ" : "s e: ",
u"そぉ" : "s o: ",
u"ざぁ" : "z a: ",
u"じぃ" : "j i: ",
u"ずぅ" : "z u: ",
u"ずゃ" : "zy a ",
u"ずゅ" : "zy u ",
u"ずょ" : "zy o ",
u"ぜぇ" : "z e: ",
u"ぞぉ" : "z o: ",
u"たぁ" : "t a: ",
u"ちぃ" : "ch i: ",
u"つぁ" : "ts a ",
u"つぃ" : "ts i ",
u"つぅ" : "ts u: ",
u"つゃ" : "ch a ",
u"つゅ" : "ch u ",
u"つょ" : "ch o ",
u"つぇ" : "ts e ",
u"つぉ" : "ts o ",
u"てぇ" : "t e: ",
u"とぉ" : "t o: ",
u"だぁ" : "d a: ",
u"ぢぃ" : "j i: ",
u"づぅ" : "d u: ",
u"づゃ" : "zy a ",
u"づゅ" : "zy u ",
u"づょ" : "zy o ",
u"でぇ" : "d e: ",
u"どぉ" : "d o: ",
u"なぁ" : "n a: ",
u"にぃ" : "n i: ",
u"ぬぅ" : "n u: ",
u"ぬゃ" : "ny a ",
u"ぬゅ" : "ny u ",
u"ぬょ" : "ny o ",
u"ねぇ" : "n e: ",
u"のぉ" : "n o: ",
u"はぁ" : "h a: ",
u"ひぃ" : "h i: ",
u"ふぅ" : "f u: ",
u"ふゃ" : "hy a ",
u"ふゅ" : "hy u ",
u"ふょ" : "hy o ",
u"へぇ" : "h e: ",
u"ほぉ" : "h o: ",
u"ばぁ" : "b a: ",
u"びぃ" : "b i: ",
u"ぶぅ" : "b u: ",
u"ふゃ" : "hy a ",
u"ぶゅ" : "by u ",
u"ふょ" : "hy o ",
u"べぇ" : "b e: ",
u"ぼぉ" : "b o: ",
u"ぱぁ" : "p a: ",
u"ぴぃ" : "p i: ",
u"ぷぅ" : "p u: ",
u"ぷゃ" : "py a ",
u"ぷゅ" : "py u ",
u"ぷょ" : "py o ",
u"ぺぇ" : "p e: ",
u"ぽぉ" : "p o: ",
u"まぁ" : "m a: ",
u"みぃ" : "m i: ",
u"むぅ" : "m u: ",
u"むゃ" : "my a ",
u"むゅ" : "my u ",
u"むょ" : "my o ",
u"めぇ" : "m e: ",
u"もぉ" : "m o: ",
u"やぁ" : "y a: ",
u"ゆぅ" : "y u: ",
u"ゆゃ" : "y a: ",
u"ゆゅ" : "y u: ",
u"ゆょ" : "y o: ",
u"よぉ" : "y o: ",
u"らぁ" : "r a: ",
u"りぃ" : "r i: ",
u"るぅ" : "r u: ",
u"るゃ" : "ry a ",
u"るゅ" : "ry u ",
u"るょ" : "ry o ",
u"れぇ" : "r e: ",
u"ろぉ" : "r o: ",
u"わぁ" : "w a: ",
u"をぉ" : "o: ",
u"う゛" : "b u ",
u"でぃ" : "d i ",
u"でぇ" : "d e: ",
u"でゃ" : "dy a ",
u"でゅ" : "dy u ",
u"でょ" : "dy o ",
u"てぃ" : "t i ",
u"てぇ" : "t e: ",
u"てゃ" : "ty a ",
u"てゅ" : "ty u ",
u"てょ" : "ty o ",
u"すぃ" : "s i ",
u"ずぁ" : "z u a ",
u"ずぃ" : "z i ",
u"ずぅ" : "z u ",
u"ずゃ" : "zy a ",
u"ずゅ" : "zy u ",
u"ずょ" : "zy o ",
u"ずぇ" : "z e ",
u"ずぉ" : "z o ",
u"きゃ" : "ky a ",
u"きゅ" : "ky u ",
u"きょ" : "ky o ",
u"しゃ" : "sh a ",
u"しゅ" : "sh u ",
u"しぇ" : "sh e ",
u"しょ" : "sh o ",
u"ちゃ" : "ch a ",
u"ちゅ" : "ch u ",
u"ちぇ" : "ch e ",
u"ちょ" : "ch o ",
u"とぅ" : "t u ",
u"とゃ" : "ty a ",
u"とゅ" : "ty u ",
u"とょ" : "ty o ",
u"どぁ" : "d o a ",
u"どぅ" : "d u ",
u"どゃ" : "dy a ",
u"どゅ" : "dy u ",
u"どょ" : "dy o ",
u"どぉ" : "d o: ",
u"にゃ" : "ny a ",
u"にゅ" : "ny u ",
u"にょ" : "ny o ",
u"ひゃ" : "hy a ",
u"ひゅ" : "hy u ",
u"ひょ" : "hy o ",
u"みゃ" : "my a ",
u"みゅ" : "my u ",
u"みょ" : "my o ",
u"りゃ" : "ry a ",
u"りゅ" : "ry u ",
u"りょ" : "ry o ",
u"ぎゃ" : "gy a ",
u"ぎゅ" : "gy u ",
u"ぎょ" : "gy o ",
u"ぢぇ" : "j e ",
u"ぢゃ" : "j a ",
u"ぢゅ" : "j u ",
u"ぢょ" : "j o ",
u"じぇ" : "j e ",
u"じゃ" : "j a ",
u"じゅ" : "j u ",
u"じょ" : "j o ",
u"びゃ" : "by a ",
u"びゅ" : "by u ",
u"びょ" : "by o ",
u"ぴゃ" : "py a ",
u"ぴゅ" : "py u ",
u"ぴょ" : "py o ",
u"うぁ" : "u a ",
u"うぃ" : "w i ",
u"うぇ" : "w e ",
u"うぉ" : "w o ",
u"ふぁ" : "f a ",
u"ふぃ" : "f i ",
u"ふぅ" : "f u ",
u"ふゃ" : "hy a ",
u"ふゅ" : "hy u ",
u"ふょ" : "hy o ",
u"ふぇ" : "f e ",
u"ふぉ" : "f o ",
u"あ" : "a ",
u"い" : "i ",
u"う" : "u ",
u"え" : "e ",
u"お" : "o ",
u"か" : "k a ",
u"き" : "k i ",
u"く" : "k u ",
u"け" : "k e ",
u"こ" : "k o ",
u"さ" : "s a ",
u"し" : "sh i ",
u"す" : "s u ",
u"せ" : "s e ",
u"そ" : "s o ",
u"た" : "t a ",
u"ち" : "ch i ",
u"つ" : "ts u ",
u"て" : "t e ",
u"と" : "t o ",
u"な" : "n a ",
u"に" : "n i ",
u"ぬ" : "n u ",
u"ね" : "n e ",
u"の" : "n o ",
u"は" : "h a ",
u"ひ" : "h i ",
u"ふ" : "f u ",
u"へ" : "h e ",
u"ほ" : "h o ",
u"ま" : "m a ",
u"み" : "m i ",
u"む" : "m u ",
u"め" : "m e ",
u"も" : "m o ",
u"ら" : "r a ",
u"り" : "r i ",
u"る" : "r u ",
u"れ" : "r e ",
u"ろ" : "r o ",
u"が" : "g a ",
u"ぎ" : "g i ",
u"ぐ" : "g u ",
u"げ" : "g e ",
u"ご" : "g o ",
u"ざ" : "z a ",
u"じ" : "j i ",
u"ず" : "z u ",
u"ぜ" : "z e ",
u"ぞ" : "z o ",
u"だ" : "d a ",
u"ぢ" : "j i ",
u"づ" : "z u ",
u"で" : "d e ",
u"ど" : "d o ",
u"ば" : "b a ",
u"び" : "b i ",
u"ぶ" : "b u ",
u"べ" : "b e ",
u"ぼ" : "b o ",
u"ぱ" : "p a ",
u"ぴ" : "p i ",
u"ぷ" : "p u ",
u"ぺ" : "p e ",
u"ぽ" : "p o ",
u"や" : "y a ",
u"ゆ" : "y u ",
u"よ" : "y o ",
u"わ" : "w a ",
u"ゐ" : "i ",
u"ゑ" : "e ",
u"ん" : "N ",
u"っ" : "q ",
u"ー" : ": ",
u"ぁ" : "a ",
u"ぃ" : "i ",
u"ぅ" : "u ",
u"ぇ" : "e ",
u"ぉ" : "o ",
u"ゎ" : "w a ",
u"ぉ" : "o ",
u"を" : "o ",
u"。" : "sp",
u"、" : "sp ",
u"？" : " ",
u"," : "sp ",
}


if __name__ == '__main__':
    main()
