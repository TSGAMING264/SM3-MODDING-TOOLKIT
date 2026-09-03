from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk

from sm3_toolkit.i18n import DEFAULT_LANGUAGE, normalize_language

# Static UI phrases that are safe to translate without changing file-format names,
# combobox values, paths, hashes, or any backend behavior.
# Technical identifiers (PCPACK/TEX/DDS/MAT/ANIM/XESM3) intentionally stay intact.
_UI = {
    "browse": {"العربية (Arabic)":"استعراض","Português (Brazil)":"Procurar","Filipino":"Mag-browse","Türkçe":"Gözat","Français":"Parcourir","Deutsch":"Durchsuchen","Español":"Examinar","Italiano":"Sfoglia","日本語":"参照","한국어":"찾아보기","Русский":"Обзор","中文":"浏览","Nederlands":"Bladeren","Polski":"Przeglądaj","Svenska":"Bläddra","हिन्दी":"ब्राउज़"},
    "open": {"العربية (Arabic)":"فتح","Português (Brazil)":"Abrir","Filipino":"Buksan","Türkçe":"Aç","Français":"Ouvrir","Deutsch":"Öffnen","Español":"Abrir","Italiano":"Apri","日本語":"開く","한국어":"열기","Русский":"Открыть","中文":"打开","Nederlands":"Openen","Polski":"Otwórz","Svenska":"Öppna","हिन्दी":"खोलें"},
    "open folder": {"العربية (Arabic)":"فتح المجلد","Português (Brazil)":"Abrir Pasta","Filipino":"Buksan ang Folder","Türkçe":"Klasörü Aç","Français":"Ouvrir le dossier","Deutsch":"Ordner öffnen","Español":"Abrir carpeta","Italiano":"Apri cartella","日本語":"フォルダーを開く","한국어":"폴더 열기","Русский":"Открыть папку","中文":"打开文件夹","Nederlands":"Map openen","Polski":"Otwórz folder","Svenska":"Öppna mapp","हिन्दी":"फ़ोल्डर खोलें"},
    "open output": {"العربية (Arabic)":"فتح الناتج","Português (Brazil)":"Abrir Saída","Filipino":"Buksan ang Output","Türkçe":"Çıktıyı Aç","Français":"Ouvrir la sortie","Deutsch":"Ausgabe öffnen","Español":"Abrir salida","Italiano":"Apri output","日本語":"出力を開く","한국어":"출력 열기","Русский":"Открыть результат","中文":"打开输出","Nederlands":"Uitvoer openen","Polski":"Otwórz wynik","Svenska":"Öppna utdata","हिन्दी":"आउटपुट खोलें"},
    "open file": {"العربية (Arabic)":"فتح ملف","Português (Brazil)":"Abrir Arquivo","Filipino":"Buksan ang File","Türkçe":"Dosya Aç","Français":"Ouvrir le fichier","Deutsch":"Datei öffnen","Español":"Abrir archivo","Italiano":"Apri file","日本語":"ファイルを開く","한국어":"파일 열기","Русский":"Открыть файл","中文":"打开文件","Nederlands":"Bestand openen","Polski":"Otwórz plik","Svenska":"Öppna fil","हिन्दी":"फ़ाइल खोलें"},
    "search": {"العربية (Arabic)":"بحث","Português (Brazil)":"Pesquisar","Filipino":"Hanapin","Türkçe":"Ara","Français":"Rechercher","Deutsch":"Suchen","Español":"Buscar","Italiano":"Cerca","日本語":"検索","한국어":"검색","Русский":"Поиск","中文":"搜索","Nederlands":"Zoeken","Polski":"Szukaj","Svenska":"Sök","हिन्दी":"खोजें"},
    "clear": {"العربية (Arabic)":"مسح","Português (Brazil)":"Limpar","Filipino":"I-clear","Türkçe":"Temizle","Français":"Effacer","Deutsch":"Leeren","Español":"Limpiar","Italiano":"Pulisci","日本語":"クリア","한국어":"지우기","Русский":"Очистить","中文":"清除","Nederlands":"Wissen","Polski":"Wyczyść","Svenska":"Rensa","हिन्दी":"साफ़ करें"},
    "clear search": {"العربية (Arabic)":"مسح البحث","Português (Brazil)":"Limpar Pesquisa","Filipino":"I-clear ang Search","Türkçe":"Aramayı Temizle","Français":"Effacer la recherche","Deutsch":"Suche leeren","Español":"Limpiar búsqueda","Italiano":"Cancella ricerca","日本語":"検索をクリア","한국어":"검색 지우기","Русский":"Очистить поиск","中文":"清除搜索","Nederlands":"Zoekopdracht wissen","Polski":"Wyczyść wyszukiwanie","Svenska":"Rensa sökning","हिन्दी":"खोज साफ़ करें"},
    "reset": {"العربية (Arabic)":"إعادة ضبط","Português (Brazil)":"Redefinir","Filipino":"I-reset","Türkçe":"Sıfırla","Français":"Réinitialiser","Deutsch":"Zurücksetzen","Español":"Restablecer","Italiano":"Reimposta","日本語":"リセット","한국어":"초기화","Русский":"Сбросить","中文":"重置","Nederlands":"Resetten","Polski":"Resetuj","Svenska":"Återställ","हिन्दी":"रीसेट"},
    "reset all": {"العربية (Arabic)":"إعادة ضبط الكل","Português (Brazil)":"Redefinir Tudo","Filipino":"I-reset Lahat","Türkçe":"Tümünü Sıfırla","Français":"Tout réinitialiser","Deutsch":"Alles zurücksetzen","Español":"Restablecer todo","Italiano":"Reimposta tutto","日本語":"すべてリセット","한국어":"모두 초기화","Русский":"Сбросить всё","中文":"全部重置","Nederlands":"Alles resetten","Polski":"Resetuj wszystko","Svenska":"Återställ allt","हिन्दी":"सब रीसेट"},
    "reload": {"العربية (Arabic)":"إعادة تحميل","Português (Brazil)":"Recarregar","Filipino":"I-reload","Türkçe":"Yeniden Yükle","Français":"Recharger","Deutsch":"Neu laden","Español":"Recargar","Italiano":"Ricarica","日本語":"再読み込み","한국어":"다시 불러오기","Русский":"Перезагрузить","中文":"重新加载","Nederlands":"Herladen","Polski":"Przeładuj","Svenska":"Ladda om","हिन्दी":"रीलोड"},
    "rescan": {"العربية (Arabic)":"إعادة الفحص","Português (Brazil)":"Verificar Novamente","Filipino":"I-scan Muli","Türkçe":"Yeniden Tara","Français":"Réanalyser","Deutsch":"Neu scannen","Español":"Reescanear","Italiano":"Riscansiona","日本語":"再スキャン","한국어":"다시 스캔","Русский":"Сканировать снова","中文":"重新扫描","Nederlands":"Opnieuw scannen","Polski":"Skanuj ponownie","Svenska":"Skanna igen","हिन्दी":"फिर स्कैन करें"},
    "preview": {"العربية (Arabic)":"معاينة","Português (Brazil)":"Prévia","Filipino":"Preview","Türkçe":"Önizleme","Français":"Aperçu","Deutsch":"Vorschau","Español":"Vista previa","Italiano":"Anteprima","日本語":"プレビュー","한국어":"미리보기","Русский":"Предпросмотр","中文":"预览","Nederlands":"Voorbeeld","Polski":"Podgląd","Svenska":"Förhandsvisa","हिन्दी":"प्रीव्यू"},
    "preview selected": {"العربية (Arabic)":"معاينة المحدد","Português (Brazil)":"Prévia Selecionada","Filipino":"I-preview ang Napili","Türkçe":"Seçileni Önizle","Français":"Aperçu sélectionné","Deutsch":"Auswahl anzeigen","Español":"Vista previa seleccionada","Italiano":"Anteprima selezionata","日本語":"選択をプレビュー","한국어":"선택 미리보기","Русский":"Предпросмотр выбранного","中文":"预览所选","Nederlands":"Selectie bekijken","Polski":"Podgląd zaznaczonego","Svenska":"Förhandsvisa val","हिन्दी":"चुना हुआ प्रीव्यू"},
    "choose folder": {"العربية (Arabic)":"اختر مجلدًا","Português (Brazil)":"Escolher Pasta","Filipino":"Pumili ng Folder","Türkçe":"Klasör Seç","Français":"Choisir un dossier","Deutsch":"Ordner wählen","Español":"Elegir carpeta","Italiano":"Scegli cartella","日本語":"フォルダーを選択","한국어":"폴더 선택","Русский":"Выбрать папку","中文":"选择文件夹","Nederlands":"Map kiezen","Polski":"Wybierz folder","Svenska":"Välj mapp","हिन्दी":"फ़ोल्डर चुनें"},
    "stop": {"العربية (Arabic)":"إيقاف","Português (Brazil)":"Parar","Filipino":"Itigil","Türkçe":"Durdur","Français":"Arrêter","Deutsch":"Stopp","Español":"Detener","Italiano":"Ferma","日本語":"停止","한국어":"중지","Русский":"Стоп","中文":"停止","Nederlands":"Stoppen","Polski":"Zatrzymaj","Svenska":"Stoppa","हिन्दी":"रोकें"},
    "info": {"العربية (Arabic)":"معلومات","Português (Brazil)":"Info","Filipino":"Info","Türkçe":"Bilgi","Français":"Info","Deutsch":"Info","Español":"Info","Italiano":"Info","日本語":"情報","한국어":"정보","Русский":"Инфо","中文":"信息","Nederlands":"Info","Polski":"Info","Svenska":"Info","हिन्दी":"जानकारी"},
    "index": {"العربية (Arabic)":"الفهرس","Português (Brazil)":"Índice","Filipino":"Index","Türkçe":"Dizin","Français":"Index","Deutsch":"Index","Español":"Índice","Italiano":"Indice","日本語":"番号","한국어":"인덱스","Русский":"Индекс","中文":"索引","Nederlands":"Index","Polski":"Indeks","Svenska":"Index","हिन्दी":"इंडेक्स"},
    "size": {"العربية (Arabic)":"الحجم","Português (Brazil)":"Tamanho","Filipino":"Laki","Türkçe":"Boyut","Français":"Taille","Deutsch":"Größe","Español":"Tamaño","Italiano":"Dimensione","日本語":"サイズ","한국어":"크기","Русский":"Размер","中文":"大小","Nederlands":"Grootte","Polski":"Rozmiar","Svenska":"Storlek","हिन्दी":"आकार"},
    "file name": {"العربية (Arabic)":"اسم الملف","Português (Brazil)":"Nome do Arquivo","Filipino":"Pangalan ng File","Türkçe":"Dosya Adı","Français":"Nom du fichier","Deutsch":"Dateiname","Español":"Nombre de archivo","Italiano":"Nome file","日本語":"ファイル名","한국어":"파일 이름","Русский":"Имя файла","中文":"文件名","Nederlands":"Bestandsnaam","Polski":"Nazwa pliku","Svenska":"Filnamn","हिन्दी":"फ़ाइल नाम"},
    "type": {"العربية (Arabic)":"النوع","Português (Brazil)":"Tipo","Filipino":"Uri","Türkçe":"Tür","Français":"Type","Deutsch":"Typ","Español":"Tipo","Italiano":"Tipo","日本語":"種類","한국어":"유형","Русский":"Тип","中文":"类型","Nederlands":"Type","Polski":"Typ","Svenska":"Typ","हिन्दी":"प्रकार"},
    "source": {"العربية (Arabic)":"المصدر","Português (Brazil)":"Fonte","Filipino":"Source","Türkçe":"Kaynak","Français":"Source","Deutsch":"Quelle","Español":"Fuente","Italiano":"Sorgente","日本語":"ソース","한국어":"소스","Русский":"Источник","中文":"来源","Nederlands":"Bron","Polski":"Źródło","Svenska":"Källa","हिन्दी":"स्रोत"},
    "list contents": {"العربية (Arabic)":"عرض المحتويات","Português (Brazil)":"Listar Conteúdo","Filipino":"Ilista ang Nilalaman","Türkçe":"İçeriği Listele","Français":"Lister le contenu","Deutsch":"Inhalt auflisten","Español":"Listar contenido","Italiano":"Elenca contenuto","日本語":"内容を一覧","한국어":"내용 목록","Русский":"Показать содержимое","中文":"列出内容","Nederlands":"Inhoud tonen","Polski":"Pokaż zawartość","Svenska":"Lista innehåll","हिन्दी":"सामग्री सूची"},
    "classic extract": {"العربية (Arabic)":"استخراج كلاسيكي","Português (Brazil)":"Extração Clássica","Filipino":"Classic Extract","Türkçe":"Klasik Çıkarma","Français":"Extraction classique","Deutsch":"Klassisch extrahieren","Español":"Extracción clásica","Italiano":"Estrazione classica","日本語":"クラシック抽出","한국어":"클래식 추출","Русский":"Обычная распаковка","中文":"经典提取","Nederlands":"Klassiek uitpakken","Polski":"Klasyczna ekstrakcja","Svenska":"Klassisk extrahering","हिन्दी":"क्लासिक एक्सट्रैक्ट"},
    "mod loader ready": {"العربية (Arabic)":"جاهز لـ Mod Loader","Português (Brazil)":"Pronto para Mod Loader","Filipino":"Mod Loader Ready","Türkçe":"Mod Loader Hazır","Français":"Prêt pour Mod Loader","Deutsch":"Mod Loader Ready","Español":"Listo para Mod Loader","Italiano":"Pronto per Mod Loader","日本語":"Mod Loader Ready","한국어":"Mod Loader Ready","Русский":"Готово для Mod Loader","中文":"Mod Loader Ready","Nederlands":"Mod Loader Ready","Polski":"Mod Loader Ready","Svenska":"Mod Loader Ready","हिन्दी":"Mod Loader Ready"},
    "pc extractor": {"العربية (Arabic)":"مستخرج PC","Português (Brazil)":"Extrator PC","Filipino":"PC Extractor","Türkçe":"PC Çıkarıcı","Français":"Extracteur PC","Deutsch":"PC-Extraktor","Español":"Extractor PC","Italiano":"Estrattore PC","日本語":"PC 抽出","한국어":"PC 추출기","Русский":"PC распаковщик","中文":"PC 提取器","Nederlands":"PC-extractor","Polski":"Ekstraktor PC","Svenska":"PC-extraktor","हिन्दी":"PC एक्सट्रैक्टर"},
    "xbox extractor (experimental)": {"العربية (Arabic)":"مستخرج Xbox (تجريبي)","Português (Brazil)":"Extrator Xbox (Experimental)","Filipino":"Xbox Extractor (Experimental)","Türkçe":"Xbox Çıkarıcı (Deneysel)","Français":"Extracteur Xbox (Expérimental)","Deutsch":"Xbox-Extraktor (Experimentell)","Español":"Extractor Xbox (Experimental)","Italiano":"Estrattore Xbox (Sperimentale)","日本語":"Xbox 抽出 (実験的)","한국어":"Xbox 추출기 (실험적)","Русский":"Xbox распаковщик (эксперимент)","中文":"Xbox 提取器（实验）","Nederlands":"Xbox-extractor (Experimenteel)","Polski":"Ekstraktor Xbox (Eksperymentalny)","Svenska":"Xbox-extraktor (Experimentell)","हिन्दी":"Xbox एक्सट्रैक्टर (प्रयोगात्मक)"},
    "texture info": {"العربية (Arabic)":"معلومات النسيج","Português (Brazil)":"Info da Textura","Filipino":"Texture Info","Türkçe":"Doku Bilgisi","Français":"Infos texture","Deutsch":"Texturinfo","Español":"Info de textura","Italiano":"Info texture","日本語":"テクスチャ情報","한국어":"텍스처 정보","Русский":"Информация о текстуре","中文":"纹理信息","Nederlands":"Texture-info","Polski":"Informacje o teksturze","Svenska":"Texturinfo","हिन्दी":"टेक्सचर जानकारी"},
    "model info": {"العربية (Arabic)":"معلومات النموذج","Português (Brazil)":"Info do Modelo","Filipino":"Model Info","Türkçe":"Model Bilgisi","Français":"Infos modèle","Deutsch":"Modellinfo","Español":"Info del modelo","Italiano":"Info modello","日本語":"モデル情報","한국어":"모델 정보","Русский":"Информация о модели","中文":"模型信息","Nederlands":"Modelinfo","Polski":"Informacje o modelu","Svenska":"Modellinfo","हिन्दी":"मॉडल जानकारी"},
    "viewport controls": {"العربية (Arabic)":"عناصر تحكم العرض","Português (Brazil)":"Controles da Visualização","Filipino":"Viewport Controls","Türkçe":"Görünüm Kontrolleri","Français":"Contrôles de vue","Deutsch":"Ansichtssteuerung","Español":"Controles de vista","Italiano":"Controlli vista","日本語":"ビュー操作","한국어":"뷰포트 조작","Русский":"Управление видом","中文":"视图控制","Nederlands":"Weergavebediening","Polski":"Sterowanie widokiem","Svenska":"Visningskontroller","हिन्दी":"व्यू कंट्रोल"},
    "solid": {"العربية (Arabic)":"مصمت","Português (Brazil)":"Sólido","Filipino":"Solid","Türkçe":"Katı","Français":"Solide","Deutsch":"Solid","Español":"Sólido","Italiano":"Solido","日本語":"ソリッド","한국어":"솔리드","Русский":"Сплошной","中文":"实体","Nederlands":"Massief","Polski":"Bryła","Svenska":"Solid","हिन्दी":"सॉलिड"},
    "wireframe": {"العربية (Arabic)":"شبكي","Português (Brazil)":"Wireframe","Filipino":"Wireframe","Türkçe":"Tel Kafes","Français":"Fil de fer","Deutsch":"Drahtmodell","Español":"Malla","Italiano":"Wireframe","日本語":"ワイヤーフレーム","한국어":"와이어프레임","Русский":"Каркас","中文":"线框","Nederlands":"Draadmodel","Polski":"Siatka","Svenska":"Trådmodell","हिन्दी":"वायरफ्रेम"},
    "grid": {"العربية (Arabic)":"شبكة","Português (Brazil)":"Grade","Filipino":"Grid","Türkçe":"Izgara","Français":"Grille","Deutsch":"Raster","Español":"Cuadrícula","Italiano":"Griglia","日本語":"グリッド","한국어":"그리드","Русский":"Сетка","中文":"网格","Nederlands":"Raster","Polski":"Siatka","Svenska":"Rutnät","हिन्दी":"ग्रिड"},
    "show all": {"العربية (Arabic)":"إظهار الكل","Português (Brazil)":"Mostrar Tudo","Filipino":"Ipakita Lahat","Türkçe":"Tümünü Göster","Français":"Tout afficher","Deutsch":"Alle anzeigen","Español":"Mostrar todo","Italiano":"Mostra tutto","日本語":"すべて表示","한국어":"모두 표시","Русский":"Показать всё","中文":"全部显示","Nederlands":"Alles tonen","Polski":"Pokaż wszystko","Svenska":"Visa alla","हिन्दी":"सब दिखाएँ"},
    "hide all": {"العربية (Arabic)":"إخفاء الكل","Português (Brazil)":"Ocultar Tudo","Filipino":"Itago Lahat","Türkçe":"Tümünü Gizle","Français":"Tout masquer","Deutsch":"Alle ausblenden","Español":"Ocultar todo","Italiano":"Nascondi tutto","日本語":"すべて非表示","한국어":"모두 숨기기","Русский":"Скрыть всё","中文":"全部隐藏","Nederlands":"Alles verbergen","Polski":"Ukryj wszystko","Svenska":"Dölj alla","हिन्दी":"सब छिपाएँ"},
    "toggle selected": {"العربية (Arabic)":"تبديل المحدد","Português (Brazil)":"Alternar Selecionado","Filipino":"I-toggle ang Napili","Türkçe":"Seçileni Değiştir","Français":"Basculer la sélection","Deutsch":"Auswahl umschalten","Español":"Alternar seleccionado","Italiano":"Attiva/disattiva selezionato","日本語":"選択を切替","한국어":"선택 전환","Русский":"Переключить выбранное","中文":"切换所选","Nederlands":"Selectie wisselen","Polski":"Przełącz zaznaczone","Svenska":"Växla val","हिन्दी":"चुना हुआ टॉगल"},
    "fit": {"العربية (Arabic)":"ملاءمة","Português (Brazil)":"Ajustar","Filipino":"Fit","Türkçe":"Sığdır","Français":"Ajuster","Deutsch":"Einpassen","Español":"Ajustar","Italiano":"Adatta","日本語":"フィット","한국어":"맞춤","Русский":"Вписать","中文":"适应","Nederlands":"Passend","Polski":"Dopasuj","Svenska":"Anpassa","हिन्दी":"फिट"},
    "save changes": {"العربية (Arabic)":"حفظ التغييرات","Português (Brazil)":"Salvar Alterações","Filipino":"I-save ang Changes","Türkçe":"Değişiklikleri Kaydet","Français":"Enregistrer les modifications","Deutsch":"Änderungen speichern","Español":"Guardar cambios","Italiano":"Salva modifiche","日本語":"変更を保存","한국어":"변경 저장","Русский":"Сохранить изменения","中文":"保存更改","Nederlands":"Wijzigingen opslaan","Polski":"Zapisz zmiany","Svenska":"Spara ändringar","हिन्दी":"बदलाव सेव करें"},
    "apply changes": {"العربية (Arabic)":"تطبيق التغييرات","Português (Brazil)":"Aplicar Alterações","Filipino":"I-apply ang Changes","Türkçe":"Değişiklikleri Uygula","Français":"Appliquer les modifications","Deutsch":"Änderungen anwenden","Español":"Aplicar cambios","Italiano":"Applica modifiche","日本語":"変更を適用","한국어":"변경 적용","Русский":"Применить изменения","中文":"应用更改","Nederlands":"Wijzigingen toepassen","Polski":"Zastosuj zmiany","Svenska":"Tillämpa ändringar","हिन्दी":"बदलाव लागू करें"},
    "previous": {"العربية (Arabic)":"السابق","Português (Brazil)":"Anterior","Filipino":"Nakaraan","Türkçe":"Önceki","Français":"Précédent","Deutsch":"Zurück","Español":"Anterior","Italiano":"Precedente","日本語":"前へ","한국어":"이전","Русский":"Назад","中文":"上一个","Nederlands":"Vorige","Polski":"Poprzedni","Svenska":"Föregående","हिन्दी":"पिछला"},
    "next": {"العربية (Arabic)":"التالي","Português (Brazil)":"Próximo","Filipino":"Susunod","Türkçe":"Sonraki","Français":"Suivant","Deutsch":"Weiter","Español":"Siguiente","Italiano":"Successivo","日本語":"次へ","한국어":"다음","Русский":"Далее","中文":"下一个","Nederlands":"Volgende","Polski":"Następny","Svenska":"Nästa","हिन्दी":"अगला"},
    "find text": {"العربية (Arabic)":"بحث عن نص","Português (Brazil)":"Buscar Texto","Filipino":"Hanapin ang Text","Türkçe":"Metin Bul","Français":"Rechercher du texte","Deutsch":"Text suchen","Español":"Buscar texto","Italiano":"Trova testo","日本語":"テキスト検索","한국어":"텍스트 찾기","Русский":"Найти текст","中文":"查找文本","Nederlands":"Tekst zoeken","Polski":"Znajdź tekst","Svenska":"Sök text","हिन्दी":"टेक्स्ट खोजें"},
    "export text": {"العربية (Arabic)":"تصدير النص","Português (Brazil)":"Exportar Texto","Filipino":"I-export ang Text","Türkçe":"Metni Dışa Aktar","Français":"Exporter le texte","Deutsch":"Text exportieren","Español":"Exportar texto","Italiano":"Esporta testo","日本語":"テキストを書き出す","한국어":"텍스트 내보내기","Русский":"Экспорт текста","中文":"导出文本","Nederlands":"Tekst exporteren","Polski":"Eksportuj tekst","Svenska":"Exportera text","हिन्दी":"टेक्स्ट एक्सपोर्ट"},
    "selected sound": {"العربية (Arabic)":"الصوت المحدد","Português (Brazil)":"Som Selecionado","Filipino":"Napiling Sound","Türkçe":"Seçili Ses","Français":"Son sélectionné","Deutsch":"Ausgewählter Sound","Español":"Sonido seleccionado","Italiano":"Audio selezionato","日本語":"選択サウンド","한국어":"선택된 사운드","Русский":"Выбранный звук","中文":"所选声音","Nederlands":"Geselecteerd geluid","Polski":"Wybrany dźwięk","Svenska":"Valt ljud","हिन्दी":"चुना हुआ साउंड"},
    "replacement audio": {"العربية (Arabic)":"الصوت البديل","Português (Brazil)":"Áudio de Substituição","Filipino":"Replacement Audio","Türkçe":"Değiştirme Sesi","Français":"Audio de remplacement","Deutsch":"Ersatz-Audio","Español":"Audio de reemplazo","Italiano":"Audio sostitutivo","日本語":"置換オーディオ","한국어":"교체 오디오","Русский":"Аудио для замены","中文":"替换音频","Nederlands":"Vervangende audio","Polski":"Audio zastępcze","Svenska":"Ersättningsljud","हिन्दी":"रिप्लेसमेंट ऑडियो"},
    "output folder": {"العربية (Arabic)":"مجلد الإخراج","Português (Brazil)":"Pasta de Saída","Filipino":"Output Folder","Türkçe":"Çıktı Klasörü","Français":"Dossier de sortie","Deutsch":"Ausgabeordner","Español":"Carpeta de salida","Italiano":"Cartella output","日本語":"出力フォルダー","한국어":"출력 폴더","Русский":"Папка вывода","中文":"输出文件夹","Nederlands":"Uitvoermap","Polski":"Folder wyjściowy","Svenska":"Utdatamapp","हिन्दी":"आउटपुट फ़ोल्डर"},
    "direct audio replace": {"العربية (Arabic)":"استبدال صوت مباشر","Português (Brazil)":"Substituição Direta de Áudio","Filipino":"Direct Audio Replace","Türkçe":"Doğrudan Ses Değiştirme","Français":"Remplacement audio direct","Deutsch":"Direkter Audio-Ersatz","Español":"Reemplazo directo de audio","Italiano":"Sostituzione audio diretta","日本語":"直接オーディオ置換","한국어":"직접 오디오 교체","Русский":"Прямая замена аудио","中文":"直接替换音频","Nederlands":"Direct audio vervangen","Polski":"Bezpośrednia zamiana audio","Svenska":"Direkt ljudersättning","हिन्दी":"डायरेक्ट ऑडियो रिप्लेस"},
    "music replacement": {"العربية (Arabic)":"استبدال الموسيقى","Português (Brazil)":"Substituição de Música","Filipino":"Music Replacement","Türkçe":"Müzik Değiştirme","Français":"Remplacement de musique","Deutsch":"Musik ersetzen","Español":"Reemplazo de música","Italiano":"Sostituzione musica","日本語":"音楽置換","한국어":"음악 교체","Русский":"Замена музыки","中文":"替换音乐","Nederlands":"Muziek vervangen","Polski":"Zamiana muzyki","Svenska":"Musikersättning","हिन्दी":"म्यूज़िक रिप्लेसमेंट"},
    "log": {"العربية (Arabic)":"السجل","Português (Brazil)":"Log","Filipino":"Log","Türkçe":"Günlük","Français":"Journal","Deutsch":"Protokoll","Español":"Registro","Italiano":"Log","日本語":"ログ","한국어":"로그","Русский":"Журнал","中文":"日志","Nederlands":"Logboek","Polski":"Dziennik","Svenska":"Logg","हिन्दी":"लॉग"},
    "close": {"العربية (Arabic)":"إغلاق","Português (Brazil)":"Fechar","Filipino":"Isara","Türkçe":"Kapat","Français":"Fermer","Deutsch":"Schließen","Español":"Cerrar","Italiano":"Chiudi","日本語":"閉じる","한국어":"닫기","Русский":"Закрыть","中文":"关闭","Nederlands":"Sluiten","Polski":"Zamknij","Svenska":"Stäng","हिन्दी":"बंद करें"},
    "cancel": {"العربية (Arabic)":"إلغاء","Português (Brazil)":"Cancelar","Filipino":"Kanselahin","Türkçe":"İptal","Français":"Annuler","Deutsch":"Abbrechen","Español":"Cancelar","Italiano":"Annulla","日本語":"キャンセル","한국어":"취소","Русский":"Отмена","中文":"取消","Nederlands":"Annuleren","Polski":"Anuluj","Svenska":"Avbryt","हिन्दी":"रद्द करें"},
    "classic workflow": {"العربية (Arabic)":"المسار الكلاسيكي","Português (Brazil)":"Fluxo Clássico","Filipino":"Classic Workflow","Türkçe":"Klasik İş Akışı","Français":"Flux classique","Deutsch":"Klassischer Ablauf","Español":"Flujo clásico","Italiano":"Flusso classico","日本語":"クラシックワークフロー","한국어":"클래식 워크플로","Русский":"Классический режим","中文":"经典工作流","Nederlands":"Klassieke workflow","Polski":"Klasyczny tryb","Svenska":"Klassiskt arbetsflöde","हिन्दी":"क्लासिक वर्कफ़्लो"},
    "browse + image": {"العربية (Arabic)":"استعراض + صورة","Português (Brazil)":"Navegar + Imagem","Filipino":"Browse + Image","Türkçe":"Gözat + Görsel","Français":"Parcourir + Image","Deutsch":"Durchsuchen + Bild","Español":"Examinar + Imagen","Italiano":"Sfoglia + Immagine","日本語":"参照 + 画像","한국어":"찾아보기 + 이미지","Русский":"Обзор + изображение","中文":"浏览 + 图像","Nederlands":"Bladeren + Afbeelding","Polski":"Przeglądaj + Obraz","Svenska":"Bläddra + Bild","हिन्दी":"ब्राउज़ + इमेज"},
}

# Add a few directional labels programmatically.
_DIRECTIONS = {
    "front": {"العربية (Arabic)":"أمام","Português (Brazil)":"Frente","Filipino":"Harap","Türkçe":"Ön","Français":"Avant","Deutsch":"Vorne","Español":"Frente","Italiano":"Fronte","日本語":"前","한국어":"정면","Русский":"Спереди","中文":"正面","Nederlands":"Voor","Polski":"Przód","Svenska":"Fram","हिन्दी":"सामने"},
    "back": {"العربية (Arabic)":"خلف","Português (Brazil)":"Trás","Filipino":"Likod","Türkçe":"Arka","Français":"Arrière","Deutsch":"Hinten","Español":"Atrás","Italiano":"Retro","日本語":"後ろ","한국어":"후면","Русский":"Сзади","中文":"背面","Nederlands":"Achter","Polski":"Tył","Svenska":"Bak","हिन्दी":"पीछे"},
    "left": {"العربية (Arabic)":"يسار","Português (Brazil)":"Esquerda","Filipino":"Kaliwa","Türkçe":"Sol","Français":"Gauche","Deutsch":"Links","Español":"Izquierda","Italiano":"Sinistra","日本語":"左","한국어":"왼쪽","Русский":"Слева","中文":"左侧","Nederlands":"Links","Polski":"Lewo","Svenska":"Vänster","हिन्दी":"बायाँ"},
    "right": {"العربية (Arabic)":"يمين","Português (Brazil)":"Direita","Filipino":"Kanan","Türkçe":"Sağ","Français":"Droite","Deutsch":"Rechts","Español":"Derecha","Italiano":"Destra","日本語":"右","한국어":"오른쪽","Русский":"Справа","中文":"右侧","Nederlands":"Rechts","Polski":"Prawo","Svenska":"Höger","हिन्दी":"दायाँ"},
}
_UI.update(_DIRECTIONS)



# v5.2.179: broader native-language vocabulary used to translate labels that
# were not explicitly listed in the older exact "safe phrase" table.
_LANG_ORDER = (
    "العربية (Arabic)", "Português (Brazil)", "Filipino", "Türkçe", "Français", "Deutsch",
    "Español", "Italiano", "日本語", "한국어", "Русский", "中文", "Nederlands", "Polski", "Svenska", "हिन्दी",
)

_MORE_UI = {}
def _add_native(key: str, *values: str) -> None:
    if len(values) != len(_LANG_ORDER):
        raise ValueError(f"translation row {key!r} has {len(values)} values")
    _MORE_UI[key.casefold()] = dict(zip(_LANG_ORDER, values))

_add_native("select", "اختر", "Selecionar", "Piliin", "Seç", "Sélectionner", "Auswählen", "Seleccionar", "Seleziona", "選択", "선택", "Выбрать", "选择", "Selecteren", "Wybierz", "Välj", "चुनें")
_add_native("select file", "اختر ملفًا", "Selecionar arquivo", "Pumili ng file", "Dosya seç", "Sélectionner un fichier", "Datei auswählen", "Seleccionar archivo", "Seleziona file", "ファイルを選択", "파일 선택", "Выбрать файл", "选择文件", "Bestand selecteren", "Wybierz plik", "Välj fil", "फ़ाइल चुनें")
_add_native("select folder", "اختر مجلدًا", "Selecionar pasta", "Pumili ng folder", "Klasör seç", "Sélectionner un dossier", "Ordner auswählen", "Seleccionar carpeta", "Seleziona cartella", "フォルダーを選択", "폴더 선택", "Выбрать папку", "选择文件夹", "Map selecteren", "Wybierz folder", "Välj mapp", "फ़ोल्डर चुनें")
_add_native("choose", "اختر", "Escolher", "Pumili", "Seç", "Choisir", "Wählen", "Elegir", "Scegli", "選ぶ", "선택", "Выбрать", "选择", "Kiezen", "Wybierz", "Välj", "चुनें")
_add_native("file", "ملف", "Arquivo", "File", "Dosya", "Fichier", "Datei", "Archivo", "File", "ファイル", "파일", "Файл", "文件", "Bestand", "Plik", "Fil", "फ़ाइल")
_add_native("folder", "مجلد", "Pasta", "Folder", "Klasör", "Dossier", "Ordner", "Carpeta", "Cartella", "フォルダー", "폴더", "Папка", "文件夹", "Map", "Folder", "Mapp", "फ़ोल्डर")
_add_native("input", "الإدخال", "Entrada", "Input", "Girdi", "Entrée", "Eingabe", "Entrada", "Ingresso", "入力", "입력", "Вход", "输入", "Invoer", "Wejście", "Indata", "इनपुट")
_add_native("output", "الإخراج", "Saída", "Output", "Çıktı", "Sortie", "Ausgabe", "Salida", "Output", "出力", "출력", "Вывод", "输出", "Uitvoer", "Wyjście", "Utdata", "आउटपुट")
_add_native("animation", "حركة", "Animação", "Animasiyon", "Animasyon", "Animation", "Animation", "Animación", "Animazione", "アニメーション", "애니메이션", "Анимация", "动画", "Animatie", "Animacja", "Animation", "एनीमेशन")
_add_native("animations", "الحركات", "Animações", "Mga animasiyon", "Animasyonlar", "Animations", "Animationen", "Animaciones", "Animazioni", "アニメーション", "애니메이션", "Анимации", "动画", "Animaties", "Animacje", "Animationer", "एनीमेशन")
_add_native("texture", "خامة", "Textura", "Texture", "Doku", "Texture", "Textur", "Textura", "Texture", "テクスチャ", "텍스처", "Текстура", "纹理", "Textuur", "Tekstura", "Textur", "टेक्सचर")
_add_native("textures", "الخامات", "Texturas", "Mga texture", "Dokular", "Textures", "Texturen", "Texturas", "Texture", "テクスチャ", "텍스처", "Текстуры", "纹理", "Texturen", "Tekstury", "Texturer", "टेक्सचर")
_add_native("model", "نموذج", "Modelo", "Modelo", "Model", "Modèle", "Modell", "Modelo", "Modello", "モデル", "모델", "Модель", "模型", "Model", "Model", "Modell", "मॉडल")
_add_native("sound", "الصوت", "Som", "Tunog", "Ses", "Son", "Ton", "Sonido", "Suono", "サウンド", "사운드", "Звук", "声音", "Geluid", "Dźwięk", "Ljud", "साउंड")
_add_native("audio", "الصوت", "Áudio", "Audio", "Ses", "Audio", "Audio", "Audio", "Audio", "オーディオ", "오디오", "Аудио", "音频", "Audio", "Audio", "Ljud", "ऑडियो")
_add_native("music", "الموسيقى", "Música", "Musika", "Müzik", "Musique", "Musik", "Música", "Musica", "音楽", "음악", "Музыка", "音乐", "Muziek", "Muzyka", "Musik", "संगीत")
_add_native("editor", "محرر", "Editor", "Patnugot", "Düzenleyici", "Éditeur", "Editor", "Editor", "Editor", "編集", "편집기", "Редактор", "编辑器", "Editor", "Edytor", "Redigerare", "संपादक")
_add_native("viewer", "عارض", "Visualizador", "Tingin", "Görüntüleyici", "Visionneuse", "Anzeige", "Visor", "Visualizzatore", "ビューア", "뷰어", "Просмотр", "查看器", "Weergave", "Przeglądarka", "Visare", "व्यूअर")
_add_native("build", "إنشاء", "Construir", "Bumuo", "Oluştur", "Construire", "Erstellen", "Crear", "Crea", "ビルド", "빌드", "Собрать", "构建", "Bouwen", "Zbuduj", "Bygg", "बनाएँ")
_add_native("rebuild", "إعادة بناء", "Reconstruir", "Muling buuin", "Yeniden oluştur", "Reconstruire", "Neu aufbauen", "Reconstruir", "Ricostruire", "再構築", "재구성", "Пересобрать", "重建", "Herbouwen", "Przebuduj", "Bygg om", "पुनर्निर्माण")
_add_native("verify", "تحقق", "Verificar", "Suriin", "Doğrula", "Vérifier", "Prüfen", "Verificar", "Verifica", "検証", "검증", "Проверить", "验证", "Controleren", "Zweryfikuj", "Verifiera", "जाँचें")
_add_native("review", "مراجعة", "Revisar", "Suriin", "İncele", "Examiner", "Überprüfen", "Revisar", "Controlla", "確認", "검토", "Проверка", "检查", "Controleren", "Przejrzyj", "Granska", "समीक्षा")
_add_native("scan", "فحص", "Verificar", "I-scan", "Tara", "Analyser", "Scannen", "Escanear", "Scansiona", "スキャン", "스캔", "Сканировать", "扫描", "Scannen", "Skanuj", "Skanna", "स्कैन")
_add_native("import", "استيراد", "Importar", "Mag-import", "İçe aktar", "Importer", "Importieren", "Importar", "Importa", "読み込み", "가져오기", "Импорт", "导入", "Importeren", "Importuj", "Importera", "इम्पोर्ट")
_add_native("export", "تصدير", "Exportar", "Mag-export", "Dışa aktar", "Exporter", "Exportieren", "Exportar", "Esporta", "書き出し", "내보내기", "Экспорт", "导出", "Exporteren", "Eksportuj", "Exportera", "एक्सपोर्ट")
_add_native("load", "تحميل", "Carregar", "I-load", "Yükle", "Charger", "Laden", "Cargar", "Carica", "読み込む", "불러오기", "Загрузить", "加载", "Laden", "Wczytaj", "Ladda", "लोड")
_add_native("save", "حفظ", "Salvar", "I-save", "Kaydet", "Enregistrer", "Speichern", "Guardar", "Salva", "保存", "저장", "Сохранить", "保存", "Opslaan", "Zapisz", "Spara", "सहेजें")
_add_native("apply", "تطبيق", "Aplicar", "Ilapat", "Uygula", "Appliquer", "Anwenden", "Aplicar", "Applica", "適用", "적용", "Применить", "应用", "Toepassen", "Zastosuj", "Tillämpa", "लागू करें")
_add_native("failed", "فشل", "Falhou", "Nabigo", "Başarısız", "Échec", "Fehlgeschlagen", "Falló", "Non riuscito", "失敗", "실패", "Ошибка", "失败", "Mislukt", "Niepowodzenie", "Misslyckades", "विफल")
_add_native("missing", "مفقود", "Ausente", "Nawawala", "Eksik", "Manquant", "Fehlt", "Falta", "Mancante", "不足", "누락", "Отсутствует", "缺少", "Ontbreekt", "Brak", "Saknas", "गायब")
_add_native("warning", "تحذير", "Aviso", "Babala", "Uyarı", "Avertissement", "Warnung", "Advertencia", "Avviso", "警告", "경고", "Предупреждение", "警告", "Waarschuwing", "Ostrzeżenie", "Varning", "चेतावनी")
_add_native("original", "الأصلي", "Original", "Orihinal", "Orijinal", "Original", "Original", "Original", "Originale", "元の", "원본", "Исходный", "原始", "Origineel", "Oryginalny", "Original", "मूल")
_add_native("clean", "نظيف", "Limpo", "Malinis", "Temiz", "Propre", "Sauber", "Limpio", "Pulito", "クリーン", "정상", "Чистый", "干净", "Schoon", "Czysty", "Ren", "साफ़")
_add_native("extracted", "مستخرج", "Extraído", "Na-extract", "Çıkarılmış", "Extrait", "Extrahiert", "Extraído", "Estratto", "抽出済み", "추출됨", "Извлечённый", "已提取", "Uitgepakt", "Wypakowany", "Extraherad", "निकाला हुआ")
_add_native("source", "المصدر", "Fonte", "Pinagmulan", "Kaynak", "Source", "Quelle", "Origen", "Sorgente", "ソース", "소스", "Источник", "来源", "Bron", "Źródło", "Källa", "स्रोत")
_add_native("target", "الهدف", "Destino", "Target", "Hedef", "Cible", "Ziel", "Destino", "Destinazione", "対象", "대상", "Цель", "目标", "Doel", "Cel", "Mål", "लक्ष्य")
_add_native("destination", "الوجهة", "Destino", "Patutunguhan", "Hedef", "Destination", "Ziel", "Destino", "Destinazione", "保存先", "대상", "Назначение", "目标位置", "Bestemming", "Miejsce docelowe", "Mål", "गंतव्य")
_add_native("results", "النتائج", "Resultados", "Mga resulta", "Sonuçlar", "Résultats", "Ergebnisse", "Resultados", "Risultati", "結果", "결과", "Результаты", "结果", "Resultaten", "Wyniki", "Resultat", "परिणाम")
_add_native("advanced", "متقدم", "Avançado", "Advanced", "Gelişmiş", "Avancé", "Erweitert", "Avanzado", "Avanzato", "詳細", "고급", "Расширенный", "高级", "Geavanceerd", "Zaawansowane", "Avancerat", "उन्नत")
_add_native("optional", "اختياري", "Opcional", "Opsyonal", "İsteğe bağlı", "Facultatif", "Optional", "Opcional", "Opzionale", "任意", "선택 사항", "Необязательно", "可选", "Optioneel", "Opcjonalne", "Valfritt", "वैकल्पिक")
_add_native("experimental", "تجريبي", "Experimental", "Eksperimental", "Deneysel", "Expérimental", "Experimentell", "Experimental", "Sperimentale", "実験的", "실험적", "Экспериментальный", "实验性", "Experimenteel", "Eksperymentalne", "Experimentellt", "प्रायोगिक")
_add_native("step", "الخطوة", "Etapa", "Hakbang", "Adım", "Étape", "Schritt", "Paso", "Passaggio", "手順", "단계", "Шаг", "步骤", "Stap", "Krok", "Steg", "चरण")
_add_native("mode", "الوضع", "Modo", "Mode", "Mod", "Mode", "Modus", "Modo", "Modalità", "モード", "모드", "Режим", "模式", "Modus", "Tryb", "Läge", "मोड")
_add_native("test", "اختبار", "Teste", "Subok", "Test", "Test", "Test", "Prueba", "Test", "テスト", "테스트", "Тест", "测试", "Test", "Test", "Test", "टेस्ट")
_add_native("patch", "تصحيح", "Patch", "Patch", "Yama", "Correctif", "Patch", "Parche", "Patch", "パッチ", "패치", "Патч", "补丁", "Patch", "Łatka", "Patch", "पैच")
_add_native("create", "إنشاء", "Criar", "Gumawa", "Oluştur", "Créer", "Erstellen", "Crear", "Crea", "作成", "만들기", "Создать", "创建", "Maken", "Utwórz", "Skapa", "बनाएँ")
_add_native("current", "الحالي", "Atual", "Kasalukuyan", "Geçerli", "Actuel", "Aktuell", "Actual", "Attuale", "現在", "현재", "Текущий", "当前", "Huidig", "Bieżący", "Aktuell", "वर्तमान")
_add_native("range", "النطاق", "Intervalo", "Saklaw", "Aralık", "Plage", "Bereich", "Rango", "Intervallo", "範囲", "범위", "Диапазон", "范围", "Bereik", "Zakres", "Intervall", "रेंज")
_add_native("start", "البداية", "Início", "Simula", "Başlangıç", "Début", "Start", "Inicio", "Inizio", "開始", "시작", "Начало", "开始", "Start", "Początek", "Start", "शुरू")
_add_native("end", "النهاية", "Fim", "Wakas", "Bitiş", "Fin", "Ende", "Fin", "Fine", "終了", "끝", "Конец", "结束", "Einde", "Koniec", "Slut", "अंत")
_add_native("frame", "إطار", "Quadro", "Frame", "Kare", "Image", "Frame", "Fotograma", "Fotogramma", "フレーム", "프레임", "Кадр", "帧", "Frame", "Klatka", "Bildruta", "फ्रेम")
_add_native("name", "الاسم", "Nome", "Pangalan", "Ad", "Nom", "Name", "Nombre", "Nome", "名前", "이름", "Имя", "名称", "Naam", "Nazwa", "Namn", "नाम")
_add_native("group", "المجموعة", "Grupo", "Grupo", "Grup", "Groupe", "Gruppe", "Grupo", "Gruppo", "グループ", "그룹", "Группа", "组", "Groep", "Grupa", "Grupp", "समूह")
_add_native("value", "القيمة", "Valor", "Halaga", "Değer", "Valeur", "Wert", "Valor", "Valore", "値", "값", "Значение", "值", "Waarde", "Wartość", "Värde", "मान")
_add_native("offset", "الإزاحة", "Deslocamento", "Offset", "Ofset", "Décalage", "Offset", "Desplazamiento", "Offset", "オフセット", "오프셋", "Смещение", "偏移", "Offset", "Przesunięcie", "Förskjutning", "ऑफ़सेट")
_add_native("line", "السطر", "Linha", "Linya", "Satır", "Ligne", "Zeile", "Línea", "Riga", "行", "줄", "Строка", "行", "Regel", "Wiersz", "Rad", "पंक्ति")
_add_native("page", "الصفحة", "Página", "Pahina", "Sayfa", "Page", "Seite", "Página", "Pagina", "ページ", "페이지", "Страница", "页面", "Pagina", "Strona", "Sida", "पृष्ठ")
_add_native("all", "الكل", "Tudo", "Lahat", "Tümü", "Tout", "Alle", "Todo", "Tutto", "すべて", "모두", "Все", "全部", "Alles", "Wszystko", "Alla", "सभी")
_add_native("show", "إظهار", "Mostrar", "Ipakita", "Göster", "Afficher", "Anzeigen", "Mostrar", "Mostra", "表示", "표시", "Показать", "显示", "Tonen", "Pokaż", "Visa", "दिखाएँ")
_add_native("hide", "إخفاء", "Ocultar", "Itago", "Gizle", "Masquer", "Ausblenden", "Ocultar", "Nascondi", "非表示", "숨기기", "Скрыть", "隐藏", "Verbergen", "Ukryj", "Dölj", "छिपाएँ")
_add_native("use", "استخدم", "Usar", "Gamitin", "Kullan", "Utiliser", "Verwenden", "Usar", "Usa", "使用", "사용", "Использовать", "使用", "Gebruiken", "Użyj", "Använd", "उपयोग")
_add_native("run", "تشغيل", "Executar", "Patakbuhin", "Çalıştır", "Exécuter", "Ausführen", "Ejecutar", "Esegui", "実行", "실행", "Запустить", "运行", "Uitvoeren", "Uruchom", "Kör", "चलाएँ")
_add_native("replacement", "البديل", "Substituição", "Kapalit", "Değiştirme", "Remplacement", "Ersatz", "Reemplazo", "Sostituzione", "置換", "교체", "Замена", "替换", "Vervanging", "Zamiana", "Ersättning", "प्रतिस्थापन")
_add_native("replace", "استبدال", "Substituir", "Palitan", "Değiştir", "Remplacer", "Ersetzen", "Reemplazar", "Sostituisci", "置換", "교체", "Заменить", "替换", "Vervangen", "Zamień", "Ersätt", "बदलें")
_add_native("changes", "التغييرات", "Alterações", "Mga pagbabago", "Değişiklikler", "Modifications", "Änderungen", "Cambios", "Modifiche", "変更", "변경 사항", "Изменения", "更改", "Wijzigingen", "Zmiany", "Ändringar", "बदलाव")
_add_native("release", "الإصدار", "Versão", "Release", "Sürüm", "Version", "Release", "Versión", "Versione", "リリース", "릴리스", "Релиз", "发布版", "Release", "Wydanie", "Version", "रिलीज़")
_add_native("workflow", "مسار العمل", "Fluxo de trabalho", "Daloy ng gawain", "İş akışı", "Flux de travail", "Arbeitsablauf", "Flujo de trabajo", "Flusso di lavoro", "作業手順", "작업 흐름", "Рабочий процесс", "工作流程", "Werkwijze", "Przepływ pracy", "Arbetsflöde", "कार्यप्रवाह")
_add_native("tools", "الأدوات", "Ferramentas", "Mga kasangkapan", "Araçlar", "Outils", "Werkzeuge", "Herramientas", "Strumenti", "ツール", "도구", "Инструменты", "工具", "Gereedschappen", "Narzędzia", "Verktyg", "टूल")
_add_native("settings", "الإعدادات", "Configurações", "Mga setting", "Ayarlar", "Paramètres", "Einstellungen", "Ajustes", "Impostazioni", "設定", "설정", "Настройки", "设置", "Instellingen", "Ustawienia", "Inställningar", "सेटिंग्स")
_add_native("controls", "عناصر التحكم", "Controles", "Mga kontrol", "Kontroller", "Commandes", "Steuerung", "Controles", "Controlli", "操作", "컨트롤", "Управление", "控件", "Bediening", "Sterowanie", "Kontroller", "नियंत्रण")
_add_native("help", "مساعدة", "Ajuda", "Tulong", "Yardım", "Aide", "Hilfe", "Ayuda", "Aiuto", "ヘルプ", "도움말", "Помощь", "帮助", "Help", "Pomoc", "Hjälp", "मदद")
_add_native("about", "حول", "Sobre", "Tungkol", "Hakkında", "À propos", "Info", "Acerca de", "Informazioni", "情報", "정보", "О программе", "关于", "Over", "O programie", "Om", "जानकारी")
_add_native("selected", "المحدد", "Selecionado", "Napili", "Seçili", "Sélectionné", "Ausgewählt", "Seleccionado", "Selezionato", "選択済み", "선택됨", "Выбранный", "已选择", "Geselecteerd", "Wybrany", "Vald", "चुना हुआ")
_add_native("safe", "آمن", "Seguro", "Ligtas", "Güvenli", "Sûr", "Sicher", "Seguro", "Sicuro", "安全", "안전", "Безопасный", "安全", "Veilig", "Bezpieczny", "Säker", "सुरक्षित")
_add_native("read only", "للقراءة فقط", "Somente leitura", "Basahin lamang", "Salt okunur", "Lecture seule", "Nur lesen", "Solo lectura", "Sola lettura", "読み取り専用", "읽기 전용", "Только чтение", "只读", "Alleen-lezen", "Tylko do odczytu", "Skrivskyddad", "केवल पढ़ने के लिए")
_add_native("view only", "عرض فقط", "Somente visualização", "Tingin lamang", "Yalnızca görüntüleme", "Affichage uniquement", "Nur anzeigen", "Solo visualización", "Solo visualizzazione", "表示のみ", "보기 전용", "Только просмотр", "仅查看", "Alleen bekijken", "Tylko podgląd", "Endast visning", "केवल देखने के लिए")
_add_native("created by", "صنعه", "Criado por", "Ginawa ni", "Oluşturan", "Créé par", "Erstellt von", "Creado por", "Creato da", "制作", "제작", "Создано", "制作", "Gemaakt door", "Stworzone przez", "Skapad av", "द्वारा बनाया गया")
_add_native("release information", "معلومات الإصدار", "Informações da versão", "Impormasyon ng release", "Sürüm bilgileri", "Informations de version", "Release-Informationen", "Información de la versión", "Informazioni sulla versione", "リリース情報", "릴리스 정보", "Информация о релизе", "发布信息", "Release-informatie", "Informacje o wydaniu", "Releaseinformation", "रिलीज़ जानकारी")
_add_native("how to use", "طريقة الاستخدام", "Como usar", "Paano gamitin", "Nasıl kullanılır", "Mode d’emploi", "Anleitung", "Cómo usar", "Come usare", "使い方", "사용 방법", "Как пользоваться", "使用方法", "Gebruiksaanwijzing", "Jak używać", "Så använder du", "कैसे उपयोग करें")
_add_native("open output folder", "فتح مجلد الإخراج", "Abrir pasta de saída", "Buksan ang output folder", "Çıktı klasörünü aç", "Ouvrir le dossier de sortie", "Ausgabeordner öffnen", "Abrir carpeta de salida", "Apri cartella di output", "出力フォルダーを開く", "출력 폴더 열기", "Открыть папку вывода", "打开输出文件夹", "Uitvoermap openen", "Otwórz folder wyjściowy", "Öppna utdatamapp", "आउटपुट फ़ोल्डर खोलें")
_add_native("browse output", "استعراض الإخراج", "Procurar saída", "I-browse ang output", "Çıktıya gözat", "Parcourir la sortie", "Ausgabe durchsuchen", "Examinar salida", "Sfoglia output", "出力を参照", "출력 찾아보기", "Обзор вывода", "浏览输出", "Uitvoer bladeren", "Przeglądaj wyjście", "Bläddra utdata", "आउटपुट ब्राउज़")
_add_native("browse folder", "استعراض المجلد", "Procurar pasta", "Mag-browse ng folder", "Klasöre gözat", "Parcourir le dossier", "Ordner durchsuchen", "Examinar carpeta", "Sfoglia cartella", "フォルダーを参照", "폴더 찾아보기", "Обзор папки", "浏览文件夹", "Map bladeren", "Przeglądaj folder", "Bläddra mapp", "फ़ोल्डर ब्राउज़")
_add_native("open externally", "فتح خارجيًا", "Abrir externamente", "Buksan sa labas", "Harici aç", "Ouvrir en externe", "Extern öffnen", "Abrir externamente", "Apri esternamente", "外部で開く", "외부에서 열기", "Открыть во внешней программе", "使用外部程序打开", "Extern openen", "Otwórz zewnętrznie", "Öppna externt", "बाहरी ऐप में खोलें")
_add_native("reveal folder", "إظهار المجلد", "Mostrar pasta", "Ipakita ang folder", "Klasörü göster", "Afficher le dossier", "Ordner anzeigen", "Mostrar carpeta", "Mostra cartella", "フォルダーを表示", "폴더 표시", "Показать папку", "显示文件夹", "Map tonen", "Pokaż folder", "Visa mapp", "फ़ोल्डर दिखाएँ")
_add_native("new", "جديد", "Novo", "Bago", "Yeni", "Nouveau", "Neu", "Nuevo", "Nuovo", "新規", "새", "Новый", "新", "Nieuw", "Nowy", "Ny", "नया")
_add_native("old", "قديم", "Antigo", "Luma", "Eski", "Ancien", "Alt", "Antiguo", "Vecchio", "旧", "기존", "Старый", "旧", "Oud", "Stary", "Gammal", "पुराना")
_add_native("quick", "سريع", "Rápido", "Mabilis", "Hızlı", "Rapide", "Schnell", "Rápido", "Rapido", "クイック", "빠른", "Быстрый", "快速", "Snel", "Szybki", "Snabb", "त्वरित")
_add_native("recommended", "موصى به", "Recomendado", "Inirerekomenda", "Önerilen", "Recommandé", "Empfohlen", "Recomendado", "Consigliato", "推奨", "권장", "Рекомендуется", "推荐", "Aanbevolen", "Zalecane", "Rekommenderas", "अनुशंसित")
_add_native("creator", "المنشئ", "Criador", "Lumikha", "Oluşturan", "Créateur", "Ersteller", "Creador", "Creatore", "制作者", "제작자", "Создатель", "作者", "Maker", "Twórca", "Skapare", "निर्माता")
_add_native("special thanks", "شكر خاص", "Agradecimentos especiais", "Espesyal na pasasalamat", "Özel teşekkürler", "Remerciements spéciaux", "Besonderer Dank", "Agradecimientos especiales", "Ringraziamenti speciali", "スペシャルサンクス", "특별 감사", "Особая благодарность", "特别感谢", "Speciale dank", "Specjalne podziękowania", "Särskilt tack", "विशेष धन्यवाद")
_add_native("inspiration", "الإلهام", "Inspiração", "Inspirasyon", "İlham", "Inspiration", "Inspiration", "Inspiración", "Ispirazione", "着想", "영감", "Вдохновение", "灵感", "Inspiratie", "Inspiracja", "Inspiration", "प्रेरणा")
_add_native("contributors", "المساهمون", "Colaboradores", "Mga nag-ambag", "Katkıda bulunanlar", "Contributeurs", "Mitwirkende", "Colaboradores", "Collaboratori", "協力者", "기여자", "Участники", "贡献者", "Bijdragers", "Współtwórcy", "Bidragsgivare", "योगदानकर्ता")
_add_native("community", "المجتمع", "Comunidade", "Komunidad", "Topluluk", "Communauté", "Community", "Comunidad", "Comunità", "コミュニティ", "커뮤니티", "Сообщество", "社区", "Community", "Społeczność", "Community", "समुदाय")
_add_native("credits", "الاعتمادات", "Créditos", "Mga kredito", "Katkılar", "Crédits", "Credits", "Créditos", "Crediti", "クレジット", "크레딧", "Авторы", "致谢", "Credits", "Autorzy", "Medverkande", "श्रेय")
_add_native("offline", "دون اتصال", "Offline", "Offline", "Çevrimdışı", "Hors ligne", "Offline", "Sin conexión", "Offline", "オフライン", "오프라인", "Офлайн", "离线", "Offline", "Offline", "Offline", "ऑफ़लाइन")
_add_native("decoder", "مفكك الترميز", "Decodificador", "Decoder", "Kod çözücü", "Décodeur", "Decoder", "Decodificador", "Decodificatore", "デコーダー", "디코더", "Декодер", "解码器", "Decoder", "Dekoder", "Avkodare", "डिकोडर")
_add_native("inspector", "أداة الفحص", "Inspetor", "Tagasuri", "İnceleyici", "Inspecteur", "Inspektor", "Inspector", "Ispettore", "インスペクター", "검사기", "Инспектор", "检查器", "Inspecteur", "Inspektor", "Inspektör", "निरीक्षक")
_add_native("skeleton", "الهيكل العظمي", "Esqueleto", "Skeleton", "İskelet", "Squelette", "Skelett", "Esqueleto", "Scheletro", "スケルトン", "스켈레톤", "Скелет", "骨架", "Skelet", "Szkielet", "Skelett", "स्केलेटन")
_add_native("editable", "قابل للتحرير", "Editável", "Mae-edit", "Düzenlenebilir", "Modifiable", "Bearbeitbar", "Editable", "Modificabile", "編集可能", "편집 가능", "Редактируемый", "可编辑", "Bewerkbaar", "Edytowalny", "Redigerbar", "संपादन योग्य")
_add_native("decode", "فك الترميز", "Decodificar", "I-decode", "Kod çöz", "Décoder", "Dekodieren", "Decodificar", "Decodifica", "デコード", "디코드", "Декодировать", "解码", "Decoderen", "Dekoduj", "Avkoda", "डिकोड")
_add_native("bone", "عظمة", "Osso", "Buto", "Kemik", "Os", "Knochen", "Hueso", "Osso", "ボーン", "본", "Кость", "骨骼", "Bot", "Kość", "Ben", "बोन")
_add_native("element", "عنصر", "Elemento", "Elemento", "Öğe", "Élément", "Element", "Elemento", "Elemento", "要素", "요소", "Элемент", "元素", "Element", "Element", "Element", "तत्व")
_add_native("axis", "المحور", "Eixo", "Axis", "Eksen", "Axe", "Achse", "Eje", "Asse", "軸", "축", "Ось", "轴", "As", "Oś", "Axel", "अक्ष")
_add_native("component", "مكوّن", "Componente", "Bahagi", "Bileşen", "Composant", "Komponente", "Componente", "Componente", "成分", "구성 요소", "Компонент", "组件", "Onderdeel", "Składnik", "Komponent", "घटक")
_add_native("delta", "التغير", "Variação", "Pagbabago", "Fark", "Delta", "Delta", "Delta", "Delta", "差分", "변화량", "Дельта", "增量", "Delta", "Delta", "Delta", "डेल्टा")
_add_native("track", "مسار", "Trilha", "Track", "İz", "Piste", "Spur", "Pista", "Traccia", "トラック", "트랙", "Дорожка", "轨道", "Spoor", "Ścieżka", "Spår", "ट्रैक")
_add_native("loaded", "محمّل", "Carregado", "Naka-load", "Yüklendi", "Chargé", "Geladen", "Cargado", "Caricato", "読み込み済み", "불러옴", "Загружен", "已加载", "Geladen", "Wczytany", "Laddad", "लोड किया गया")
_add_native("set", "تعيين", "Definir", "Itakda", "Ayarla", "Définir", "Setzen", "Establecer", "Imposta", "設定", "설정", "Задать", "设置", "Instellen", "Ustaw", "Ställ in", "सेट")
_add_native("filter", "تصفية", "Filtro", "Salain", "Filtre", "Filtre", "Filter", "Filtro", "Filtro", "フィルター", "필터", "Фильтр", "筛选", "Filter", "Filtr", "Filter", "फ़िल्टर")
_add_native("add", "إضافة", "Adicionar", "Idagdag", "Ekle", "Ajouter", "Hinzufügen", "Añadir", "Aggiungi", "追加", "추가", "Добавить", "添加", "Toevoegen", "Dodaj", "Lägg till", "जोड़ें")
_add_native("voice", "الصوت البشري", "Voz", "Boses", "Ses", "Voix", "Stimme", "Voz", "Voce", "音声", "음성", "Голос", "人声", "Stem", "Głos", "Röst", "आवाज़")
_add_native("dialogue", "الحوار", "Diálogo", "Diyalogo", "Diyalog", "Dialogue", "Dialog", "Diálogo", "Dialogo", "台詞", "대사", "Диалог", "对白", "Dialoog", "Dialog", "Dialog", "संवाद")
_add_native("theme", "المظهر", "Tema", "Tema", "Tema", "Thème", "Theme", "Tema", "Tema", "テーマ", "테마", "Тема", "主题", "Thema", "Motyw", "Tema", "थीम")
_add_native("parameter", "المعامل", "Parâmetro", "Parameter", "Parametre", "Paramètre", "Parameter", "Parámetro", "Parametro", "パラメーター", "매개변수", "Параметр", "参数", "Parameter", "Parametr", "Parameter", "पैरामीटर")
_add_native("context", "السياق", "Contexto", "Konteksto", "Bağlam", "Contexte", "Kontext", "Contexto", "Contesto", "コンテキスト", "컨텍스트", "Контекст", "上下文", "Context", "Kontekst", "Sammanhang", "संदर्भ")


_add_native("rebuilt", "معاد البناء", "Reconstruído", "Muling binuo", "Yeniden oluşturulmuş", "Reconstruit", "Neu aufgebaut", "Reconstruido", "Ricostruito", "再構築済み", "재구성됨", "Пересобранный", "已重建", "Herbouwd", "Przebudowany", "Ombyggd", "पुनर्निर्मित")
_add_native("open rebuilt folder", "فتح المجلد المعاد بناؤه", "Abrir pasta reconstruída", "Buksan ang muling binuong folder", "Yeniden oluşturulan klasörü aç", "Ouvrir le dossier reconstruit", "Neu aufgebauten Ordner öffnen", "Abrir carpeta reconstruida", "Apri cartella ricostruita", "再構築済みフォルダーを開く", "재구성된 폴더 열기", "Открыть папку пересборки", "打开重建文件夹", "Herbouwde map openen", "Otwórz przebudowany folder", "Öppna ombyggd mapp", "पुनर्निर्मित फ़ोल्डर खोलें")
_add_native("missing extracted folder", "مجلد الاستخراج مفقود", "Pasta extraída ausente", "Nawawala ang na-extract na folder", "Çıkarılmış klasör eksik", "Dossier extrait manquant", "Extrahierter Ordner fehlt", "Falta la carpeta extraída", "Cartella estratta mancante", "抽出済みフォルダーがありません", "추출된 폴더가 없습니다", "Отсутствует извлечённая папка", "缺少已提取文件夹", "Uitgepakte map ontbreekt", "Brak wypakowanego folderu", "Extraherad mapp saknas", "निकाला हुआ फ़ोल्डर गायब है")
_add_native("build + verify animation", "إنشاء الحركة والتحقق منها", "Construir e verificar animação", "Bumuo at suriin ang animasiyon", "Animasyonu oluştur ve doğrula", "Construire et vérifier l’animation", "Animation erstellen und prüfen", "Crear y verificar animación", "Crea e verifica animazione", "アニメーションをビルドして検証", "애니메이션 빌드 및 검증", "Собрать и проверить анимацию", "构建并验证动画", "Animatie bouwen en controleren", "Zbuduj i zweryfikuj animację", "Bygg och verifiera animation", "एनीमेशन बनाएँ और जाँचें")
_add_native("advanced controls (optional)", "عناصر تحكم متقدمة (اختياري)", "Controles avançados (opcional)", "Mga advanced na kontrol (opsyonal)", "Gelişmiş kontroller (isteğe bağlı)", "Commandes avancées (facultatif)", "Erweiterte Steuerung (optional)", "Controles avanzados (opcional)", "Controlli avanzati (opzionale)", "詳細操作（任意）", "고급 컨트롤(선택 사항)", "Расширенное управление (необязательно)", "高级控制（可选）", "Geavanceerde bediening (optioneel)", "Zaawansowane sterowanie (opcjonalne)", "Avancerade kontroller (valfritt)", "उन्नत नियंत्रण (वैकल्पिक)")
_add_native("select output folder", "اختر مجلد الإخراج", "Selecionar pasta de saída", "Piliin ang output folder", "Çıktı klasörünü seç", "Sélectionner le dossier de sortie", "Ausgabeordner auswählen", "Seleccionar carpeta de salida", "Seleziona cartella di output", "出力フォルダーを選択", "출력 폴더 선택", "Выбрать папку вывода", "选择输出文件夹", "Uitvoermap selecteren", "Wybierz folder wyjściowy", "Välj utdatamapp", "आउटपुट फ़ोल्डर चुनें")
_add_native("open rebuilt ANIM folder", "فتح مجلد ANIM المعاد بناؤه", "Abrir pasta do ANIM reconstruído", "Buksan ang folder ng muling binuong ANIM", "Yeniden oluşturulan ANIM klasörünü aç", "Ouvrir le dossier ANIM reconstruit", "Ordner der neu aufgebauten ANIM öffnen", "Abrir carpeta del ANIM reconstruido", "Apri cartella dell’ANIM ricostruito", "再構築済みANIMフォルダーを開く", "재구성된 ANIM 폴더 열기", "Открыть папку пересобранного ANIM", "打开已重建 ANIM 文件夹", "Map van herbouwde ANIM openen", "Otwórz folder przebudowanego ANIM", "Öppna mappen för ombyggd ANIM", "पुनर्निर्मित ANIM फ़ोल्डर खोलें")

# Prefer these broader entries over older exact entries when both exist.
for _k, _v in _MORE_UI.items():
    _UI.setdefault(_k, _v)

_TECH_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9_])(?:PCPACK|PCAPK|APKF|TEX|DDS|MAT|ANIM|XESM3|ASKL|NAS|CSV|JSON|XML|YAML|TOML|HTML|TXT|DOCX|ODT|RTF|FSB3|PCSSB|Ghidra|SM3|SM2|WOS|Xbox|PC|T36|DXT\d)(?![A-Za-z0-9_])"
    r"|0x[0-9A-Fa-f]+|\*\.[A-Za-z0-9_* .]+|\.[A-Za-z0-9]{2,5}(?=\b|$)"
)

_NUMBERED = re.compile(r"^(\d+\)\s*)(.+)$")


def _protect_technical(text: str) -> tuple[str, dict[str, str]]:
    protected: dict[str, str] = {}
    def repl(match: re.Match[str]) -> str:
        key = f"§§{len(protected)}§§"
        protected[key] = match.group(0)
        return key
    return _TECH_RE.sub(repl, text), protected


def _restore_technical(text: str, protected: dict[str, str]) -> str:
    for key, value in protected.items():
        text = text.replace(key, value)
    return text


def _replace_phrase(text: str, source: str, target: str) -> str:
    # English UI phrases are ASCII; boundaries keep small keys such as "all"
    # from changing pieces of filenames or unrelated words.
    pattern = re.compile(r"(?i)(?<![A-Za-z0-9_])" + re.escape(source) + r"(?![A-Za-z0-9_])")
    return pattern.sub(lambda _m: target, text)


def translate_ui_text(language: str | None, text: str) -> str:
    """Translate visible toolkit chrome while preserving technical identifiers.

    v5.2.179 no longer requires an entire label to exist in the exact phrase
    table. Exact/native phrases are preferred, then known phrases/words are
    translated inside larger labels, dialog messages and status text.
    """
    lang = normalize_language(language)
    original = str(text)
    if lang == DEFAULT_LANGUAGE:
        return original
    stripped = original.strip()
    if not stripped:
        return original

    # Exact phrase first (with numbered-prefix and trailing-colon handling).
    prefix = ""
    body = stripped
    m = _NUMBERED.match(body)
    if m:
        prefix, body = m.group(1), m.group(2)
    suffix = ""
    if body.endswith(":"):
        body, suffix = body[:-1].rstrip(), ":"
    table = _UI.get(body.casefold())
    if table is not None and table.get(lang):
        return prefix + table[lang] + suffix

    work, protected = _protect_technical(original)
    # Translate longest phrases first so "output folder" wins over "folder".
    entries: list[tuple[str, str]] = []
    for source, translations in _UI.items():
        translated = translations.get(lang)
        if translated:
            entries.append((source, translated))
    entries.sort(key=lambda item: (len(item[0].split()), len(item[0])), reverse=True)
    for source, translated in entries:
        work = _replace_phrase(work, source, translated)
    return _restore_technical(work, protected)


def _translate_notebook(widget: ttk.Notebook, language: str) -> None:
    # Main notebook is handled by app.py because it has responsive compact names.
    try:
        if str(widget.cget("style")) == "Main.TNotebook":
            return
    except Exception:
        pass
    bases = getattr(widget, "_sm3_i18n_tab_bases", {})
    try:
        for tab_id in widget.tabs():
            if tab_id not in bases:
                bases[tab_id] = str(widget.tab(tab_id, "text"))
            base = bases.get(tab_id)
            if base is not None:
                widget.tab(tab_id, text=translate_ui_text(language, base))
        widget._sm3_i18n_tab_bases = bases
    except Exception:
        pass


def _translate_tree_headings(widget: ttk.Treeview, language: str) -> None:
    bases = getattr(widget, "_sm3_i18n_heading_bases", {})
    try:
        columns = ["#0"] + list(widget.cget("columns"))
        for col in columns:
            try:
                current = str(widget.heading(col).get("text", ""))
            except Exception:
                continue
            if col not in bases:
                bases[col] = current
            base = bases.get(col)
            if base is not None:
                widget.heading(col, text=translate_ui_text(language, base), anchor=("e" if language == "العربية (Arabic)" else "center"))
        widget._sm3_i18n_heading_bases = bases
    except Exception:
        pass


def _apply_direction(widget: tk.Misc, language: str) -> None:
    """Apply readable Arabic right-to-left presentation without changing data."""
    rtl = language == "العربية (Arabic)"
    try:
        keys = widget.keys()
    except Exception:
        keys = ()

    # Save original alignment once so switching back is fully reversible.
    for option in ("anchor", "justify"):
        if option in keys:
            attr = f"_sm3_i18n_orig_{option}"
            if not hasattr(widget, attr):
                try:
                    setattr(widget, attr, widget.cget(option))
                except Exception:
                    pass
            try:
                if rtl:
                    widget.configure(**{option: "e" if option == "anchor" else "right"})
                elif hasattr(widget, attr):
                    widget.configure(**{option: getattr(widget, attr)})
            except Exception:
                pass

    # Text widgets have no widget-level justify option; use a display tag only.
    if isinstance(widget, tk.Text):
        try:
            widget.tag_configure("sm3_i18n_rtl", justify="right" if rtl else "left")
            if rtl:
                widget.tag_add("sm3_i18n_rtl", "1.0", "end")
            else:
                widget.tag_remove("sm3_i18n_rtl", "1.0", "end")
        except Exception:
            pass


def translate_widget_tree(root: tk.Misc, language: str | None) -> None:
    """Translate visible Tk/ttk chrome only when a non-English language is active.

    English is the protected baseline. On a normal English launch this function
    does not claim, rewrite, align, or otherwise touch widget text. If the user
    manually switches back to English in the same session, only values that were
    previously localized are restored.
    """
    lang = normalize_language(language)

    def restore(widget: tk.Misc) -> None:
        # Restore Arabic alignment only if localization previously changed it.
        try:
            _apply_direction(widget, DEFAULT_LANGUAGE)
        except Exception:
            pass

        if isinstance(widget, ttk.Notebook):
            try:
                if str(widget.cget("style")) != "Main.TNotebook":
                    bases = getattr(widget, "_sm3_i18n_tab_bases", {})
                    for tab_id, base in list(bases.items()):
                        try:
                            widget.tab(tab_id, text=base)
                        except Exception:
                            pass
            except Exception:
                pass

        if isinstance(widget, ttk.Treeview):
            try:
                bases = getattr(widget, "_sm3_i18n_heading_bases", {})
                for col, base in list(bases.items()):
                    try:
                        widget.heading(col, text=base, anchor="center")
                    except Exception:
                        pass
            except Exception:
                pass

        if isinstance(widget, (tk.Tk, tk.Toplevel)):
            try:
                if hasattr(widget, "_sm3_i18n_base_title"):
                    widget.title(widget._sm3_i18n_base_title)
            except Exception:
                pass

        try:
            if hasattr(widget, "_sm3_i18n_base_text") and "text" in widget.keys():
                widget.configure(text=widget._sm3_i18n_base_text)
        except Exception:
            pass

        try:
            for child in widget.winfo_children():
                restore(child)
        except Exception:
            pass

    # Critical stability rule: on a fresh English launch, localization is a no-op.
    # Only run restore if this tree was actually localized earlier in the session.
    if lang == DEFAULT_LANGUAGE:
        if getattr(root, "_sm3_i18n_was_active", False):
            restore(root)
            root._sm3_i18n_was_active = False
        return

    root._sm3_i18n_was_active = True

    def walk(widget: tk.Misc) -> None:
        _apply_direction(widget, lang)
        if isinstance(widget, ttk.Notebook):
            _translate_notebook(widget, lang)
        if isinstance(widget, ttk.Treeview):
            _translate_tree_headings(widget, lang)

        if isinstance(widget, (tk.Tk, tk.Toplevel)):
            try:
                base_title = getattr(widget, "_sm3_i18n_base_title", None)
                current_title = widget.title()
                last_title = getattr(widget, "_sm3_i18n_last_title", None)
                if base_title is None or (last_title is not None and current_title != last_title):
                    base_title = current_title
                    widget._sm3_i18n_base_title = base_title
                rendered_title = translate_ui_text(lang, base_title)
                widget.title(rendered_title)
                widget._sm3_i18n_last_title = rendered_title
            except Exception:
                pass

        try:
            keys = widget.keys()
        except Exception:
            keys = ()
        if "text" in keys:
            try:
                current = str(widget.cget("text"))
                base = getattr(widget, "_sm3_i18n_base_text", None)
                last_rendered = getattr(widget, "_sm3_i18n_last_text", None)
                # If the tool itself changed a dynamic English label since the
                # previous localization pass, treat that new value as the base.
                if base is None or (last_rendered is not None and current != last_rendered):
                    base = current
                    widget._sm3_i18n_base_text = base
                rendered = translate_ui_text(lang, base)
                widget.configure(text=rendered)
                widget._sm3_i18n_last_text = rendered
            except Exception:
                pass

        try:
            for child in widget.winfo_children():
                walk(child)
        except Exception:
            pass

    walk(root)


_DIALOG_PATCHED = False
_DIALOG_LANGUAGE_GETTER = None


def install_dialog_localization(language_getter) -> None:
    """Localize tkinter message boxes and file-dialog titles globally.

    This only changes human-facing titles/messages. Paths, file patterns and
    returned values are never translated.
    """
    global _DIALOG_PATCHED, _DIALOG_LANGUAGE_GETTER
    _DIALOG_LANGUAGE_GETTER = language_getter
    if _DIALOG_PATCHED:
        return
    _DIALOG_PATCHED = True
    from tkinter import messagebox, filedialog, simpledialog

    def lang() -> str:
        try:
            return normalize_language(_DIALOG_LANGUAGE_GETTER())
        except Exception:
            return DEFAULT_LANGUAGE

    for name in ("showinfo", "showwarning", "showerror", "askquestion", "askokcancel", "askyesno", "askyesnocancel", "askretrycancel"):
        original = getattr(messagebox, name, None)
        if original is None:
            continue
        def make_wrapper(fn):
            def wrapper(title=None, message=None, *args, **kwargs):
                active = lang()
                if title is not None:
                    title = translate_ui_text(active, str(title))
                if message is not None:
                    message = translate_ui_text(active, str(message))
                return fn(title, message, *args, **kwargs)
            return wrapper
        setattr(messagebox, name, make_wrapper(original))

    for name in ("askopenfilename", "askopenfilenames", "asksaveasfilename", "askdirectory"):
        original = getattr(filedialog, name, None)
        if original is None:
            continue
        def make_fd_wrapper(fn):
            def wrapper(*args, **kwargs):
                active = lang()
                if kwargs.get("title"):
                    kwargs["title"] = translate_ui_text(active, str(kwargs["title"]))
                # Translate display names only; never touch glob patterns.
                if kwargs.get("filetypes"):
                    try:
                        kwargs["filetypes"] = [(translate_ui_text(active, str(label)), pattern) for label, pattern in kwargs["filetypes"]]
                    except Exception:
                        pass
                return fn(*args, **kwargs)
            return wrapper
        setattr(filedialog, name, make_fd_wrapper(original))

    for name in ("askstring", "askinteger", "askfloat"):
        original = getattr(simpledialog, name, None)
        if original is None:
            continue
        def make_sd_wrapper(fn):
            def wrapper(title, prompt, *args, **kwargs):
                active = lang()
                return fn(translate_ui_text(active, str(title)), translate_ui_text(active, str(prompt)), *args, **kwargs)
            return wrapper
        setattr(simpledialog, name, make_sd_wrapper(original))
