Приложение № 1 към чл. 1, ал. 2
Критерии за формиране наименованията и конструкцията на данните на дефинициите на информационните обекти в XML формат
I. Общи изисквания
1. За описание на XML структурата на информационните обекти трябва да се използва стандартът XML Schema Definition Language (XSD) 1.0, основан на Препоръка XML Schema на Работна група "XML Schema Working Group" на консорциума W3C.
Допълнителна информация:
Вж. http://www.w3.org/XML/Schema
2. Обстоятелството "XML дефиниция" на всеки един информационен обект от вид "номенклатура", "стойност" и "сегмент" трябва да съдържа добре формиран и валиден XML Schema документ. В случай че се използват дефиниции на други информационни обекти, тези обекти трябва да са вече вписани в регистъра на информационните обекти или да са обекти, заявени за вписване със същото заявление.
3. За енкодинг на XML дефиницията трябва да се използва UTF-8:
Пример:
1 <?xml version="1.0" encoding="UTF-8"?>
2 <xsd:schema ......
UTF-8 е Unicode базиран енкодинг, който позволява използване на всички букви не само от българския език, но от всички езици, които се поддържат от него.
4. За всеки глобален тип и глобален елемент в рамките на XML дефиницията трябва да е предоставено описание на български език, поясняващо предназначението на съответния тип или елемент. Описанието трябва да е предоставено чрез използването на "documentation" елемент в рамките на "annotation" елемента, определен от XML Schema стандарта. Атрибутът "xml:lang" на елемента "documentation" трябва да присъства задължително със стойност "bg".
Пример:
1 <?xml version="1.0" encoding="UTF-8"?>
2 <xsd:schema targetNamespace="http://ereg.egov.bg/value/0008-000022"
3 xmlns="http://ereg.egov.bg/value/0008-000022"
4 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
5 elementFormDefault="qualified"
6 attributeFormDefault="unqualified">
7
8 <xsd:simpleType name="pseudonim">
9 <xsd:annotation>
10 <xsd:documentation xml:lang="bg">Псевдоним на регистрирано →
физическо лице
11 </xsd:documentation>
12 </xsd:annotation>
13 <xsd:restriction base="xsd:string"/>
14 </xsd:simpleType>
15 </xsd:schema>
II. Изисквания към типовете данни
1. В XML дефиницията на един информационен обект трябва да се използват типове данни, които възможно най-точно описват характера на данните, съдържащи се в информационния обект:
а) за описание на дати трябва да се използва вграденият в XML Schema тип "date" или производен на него;
б) за описание на дати с час трябва да се използва вграденият в XML Schema тип "datetime" или производен на него;
в) за описание на числени обекти трябва да се използват вградените в XML Schema типове "decimal", "float" или "double" или производни на тях.
2. XML дефиницията на информационен обект от вид "номенклатура" трябва да съдържа на глобално ниво дефиницията на един прост тип ("simpleType"), производен от вградения в XML Schema тип "string". Допълнително XML дефиницията може да съдържа и декларацията на един елемент от този тип. Типът трябва да съдържа списъка от уникалните регистрови идентификатори (УРИ) на термините в състава на номенклатурата.
Пример:
1 <?xml version="1.0" encoding="UTF-8"?>
2 <xsd:schema targetNamespace="http://ereg.egov.bg/nomenclature/0007-000022"
3 xmlns="http://ereg.egov.bg/ nomenclature/0007-000022"
4 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
5 elementFormDefault="qualified"
6 attributeFormDefault="unqualified">
7
8 <xsd:simpleType name="Gender">
9 <xsd:annotation>
10 <xsd:documentation>Пол на физическо лице
11 </xsd:documentation>
12 </xsd:annotation>
13 <xsd:restriction base="xsd:string">
14 <xsd:enumeration value="0006-000003"/>
15 <xsd:enumeration value="0006-000004"/>
16 <xsd:enumeration value="0006-000005"/>
17 </xsd:restriction>
18 </xsd:simpleType>
19 </xsd:schema>
3. XML дефиницията на информационен обект от вид "стойност" трябва да съдържа на глобално ниво дефиницията на един тип от изброените по-долу варианти. Допълнително XML дефиницията може да съдържа и декларацията на един елемент от този тип:
а) прост тип ("simpleType"):
Пример:
1 <?xml version="1.0" encoding="UTF-8"?>
2 <xsd:schema targetNamespace="http://ereg.egov.bg/value/0008-000033"
3 xmlns="http://ereg.egov.bg/value/0008-000033"
4 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
5 elementFormDefault="qualified"
6 attributeFormDefault="unqualified">
7
8 <xsd:simpleType name="Age">
9 <xsd:annotation>
10 <xsd:documentation>Възраст на физическо лице
11 </xsd:documentation>
12 </xsd:annotation>
13 <xsd:restriction base="xsd:integer">
14 <xsd:minInclusive value="0"/>
15 <xsd:maxInclusive value="150"/>
16 </xsd:restriction>
17 </xsd:simpleType>
18 </xsd:schema>
б) съставен тип ("complexType"), определящ празен елемент:
Пример:
1 <?xml version="1.0" encoding="UTF-8"?>
2 <xsd:schema targetNamespace="http://ereg.egov.bg/value/0008-000034"
3 xmlns="http://ereg.egov.bg/value/0008-000034"
4 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
5 elementFormDefault="qualified"
6 attributeFormDefault="unqualified">
7
8 <xsd:complexType name="EmptyType">
9 <xsd:annotation>
10 <xsd:documentation>Пример за празен елемент
11 </xsd:documentation>
12 </xsd:annotation>
13 </xsd:complexType>
14 </xsd:schema>
в) съставен тип ("complexType"), определящ елемент само с текст:
Пример:
1 <?xml version="1.0" encoding="UTF-8"?>
2 <xsd:schema targetNamespace="http://ereg.egov.bg/value/0008-000035"
3 xmlns="http://ereg.egov.bg/value/0008-000035"
4 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
5 elementFormDefault="qualified"
6 attributeFormDefault="unqualified">
7
8 <xsd:complexType name="TextOnlyType">
9 <xsd:annotation>
10 <xsd:documentation>Пример за елемент, съдържащ само текст
11 </xsd:documentation>
12 </xsd:annotation>
13 <xsd:simpleContent>
14 <xsd:extension base="xsd:unsignedByte">
15 <xsd:attribute name="used"/>
16 </xsd:extension>
17 </xsd:simpleContent>
18 </xsd:complexType>
19 </xsd:schema>
4. XML дефиницията на информационен обект от вид "сегмент" трябва да съдържа на глобално ниво дефиницията на един или повече съставни типа ("complexType"). Допълнително XML дефиницията може да съдържа и декларацията на един елемент от един от тези типове.
5. Списъци, които съдържат йерархия или код, трябва да се заявят за вписване като пакет от данни в регистъра на регистрите и данните.
6. Списъци, които не съдържат йерархия или код, трябва да се заявят за вписване като номенклатури. По изключение такъв списък може да се заяви за вписване като информационен обект от вид стойност.
III. Конвенция за именуване
1. Имената на типове или елементи в XML дефинициите на информационните обекти трябва да включват символи само от следния набор:
а) "A - Z" - големи букви от латинската азбука;
б) "a - z" - малки букви от латинската азбука;
в) "0 - 9" - цифри от 0 до 9;
г) "-" - тире;
д) "." - точка;
е) "_" - знак за подчертаване.
Пример:
1 <?xml version="1.0" encoding="UTF-8"?>
2 <xsd:schema targetNamespace="http://ereg.egov.bg/value/0008-000022"
3 xmlns="http://ereg.egov.bg/value/0008-000022"
4 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
5 elementFormDefault="qualified"
6 attributeFormDefault="unqualified">
7
8 <xsd:simpleType name="pseudonim">
9 <xsd:annotation>
10 <xsd:documentation>Псевдоним на регистрирано физическо лице
11 </xsd:documentation>
12 </xsd:annotation>
13 <xsd:restriction base="xsd:string"/>
14 </xsd:simpleType>
15 </xsd:schema>
2. Пространството от имена на самата XML Schema ("http://www.w3.org/2001/XMLSchema") трябва да се използва с префикса "xsd".
Пример:
1 <?xml version="1.0" encoding="UTF-8"?>
2 <xsd:schema targetNamespace="http://ereg.egov.bg/value/0008-000022"
3 xmlns="http://ereg.egov.bg/value/0008-000022"
4 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
5 elementFormDefault="qualified"
6 attributeFormDefault="unqualified">
7 ...........
IV. Изисквания към пространствата от имена (namespaces)
1. XML дефиницията на всеки информационен обект трябва да определя собствено, уникално пространство от имена ("namespace"). Начинът на формиране на пространството от имена се определя по следния начин, в зависимост от вида на информационния обект: (по-долу <objectURI> е уникалният регистров идентификатор (УРИ) на съответния информационен обект):
а) за информационен обект от вид "номенклатура" пространството от имена има вида:
http://ereg.egov.bg/nomenclature/<objectURI>,
например за номенклатура с УРИ 0007-000041 пространството от имена е
http://ereg.egov.bg/nomenclature/0007-000041;
Пример:
1 <?xml version="1.0" encoding="UTF-8"?>
2 <xsd:schema targetNamespace="http://ereg.egov.bg/nomenclature/0007-000041" ...
б) за информационен обект от вид "стойност" пространството от имена има вида:
http://ereg.egov.bg/value/<objectURI>,
например за стойност с УРИ 0008-000276 пространството от имена е
http://ereg.egov.bg/value/0008-000276;
Пример:
1 <?xml version="1.0" encoding="UTF-8"?>
2 <xsd:schema targetNamespace="http://ereg.egov.bg/value/0008-000276"
в) за информационен обект от вида "сегмент" пространството от имена има вида:
http://ereg.egov.bg/segment/<objectURI>,
например за сегмент с УРИ 0009-000203 пространството от имена е
http://ereg.egov.bg/segment/0009-000203.
Пример:
1 <?xml version="1.0" encoding="UTF-8"?>
2 <xsd:schema targetNamespace="http://ereg.egov.bg/segment/0009-000203" ...
2. При заявления за вписване на нов информационен обект неговият УРИ е все още неопределен. В тези случаи в описанието на пространството от имена, свързано със заявения за вписване обект, се използва поредният номер на информационния обект в заявлението за вписване във формата "R-<NNNN>", където <NNNN> e поредният номер на информационния обект в заявлението. Например:
http://ereg.egov.bg/nomenclature/R-0023
http://ereg.egov.bg/value/R-0034
http://ereg.egov.bg/segment/R-0012
Пример:
1 <?xml version="1.0" encoding="UTF-8"?>
2 <xsd:schema targetNamespace="http://ereg.egov.bg/segment/R-0023" ...
3. Горните правила за определяне на пространството от имена не се прилагат, когато вписваните схеми на информационни обекти са предмет на авторско право или по друга причина не допускат използването им чрез пространство на имена, различно от оригиналното. Изключение са и служебните пространства от имена "http://www.w3.org/2001/XMLSchema" и "http://www.w3.org/2001/XMLSchema-instance".
V. Референции към други информационни обекти
1. XML дефинициите на вече вписани в регистрите други информационни обекти, използвани в дефинициите на даден информационен обект, трябва да се включват чрез използване на XML Schema елемента <import>:
Пример:
1 <?xml version="1.0" encoding="UTF-8"?>
2 <xsd:schema targetNamespace="http://ereg.egov.bg/segment/0009-000090"
3 xmlns="http://ereg.egov.bg/segment/0009-000090"
4 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
5 xmlns:m="http://ereg.egov.bg/value/0008-000004"
6 elementFormDefault="qualified"
7 attributeFormDefault="unqualified">
8
9 <xsd:import namespace="http://ereg.egov.bg/value/0008-000004">
10 …………
2. При използването на "import" елемента не трябва да присъства атрибутът "schemaLocation".
3. В случай на необходимост от рефериране на информационен обект, заявен за вписване със същото заявление, в XML дефинициите вместо УРИ на реферирания обект трябва да се използва поредният номер на този обект от заявлението за вписване чрез следния формат:
"R-<NNNN>", където <NNNN> e поредният номер на информационния обект в заявлението за вписване.
Например: нов информационен обект от тип "стойност" с пореден номер в заявлението "15" се реферира чрез следното пространство от имена:
http://ereg.egov.bg/value/R-0015
Пример:
1 <?xml version="1.0" encoding="UTF-8"?>
2 <xsd:schema targetNamespace="http://ereg.egov.bg/segment/R-0012"
3 xmlns="http://ereg.egov.bg/segment/R-0012"
4 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
5 xmlns:m="http://ereg.egov.bg/value/R-0015"
6 elementFormDefault="qualified"
7 attributeFormDefault="unqualified">
8
9 <xsd:import namespace="http://ereg.egov.bg/value/R-0015">
10 …………
4. Ако в XML дефиницията на номенклатура се използват термини, заявени за вписване със същото заявление, то вместо УРИ на съответния термин се използва форматът "R-<NNNN>", където <NNNN> e поредният номер на термина в заявлението за вписване.
Пример:
1 <?xml version="1.0" encoding="UTF-8"?>
2 <xsd:schema targetNamespace="http://ereg.egov.bg/nomenclature/R-0043"
3 xmlns="http://ereg.egov.bg/ nomenclature/R-0043"
4 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
5 elementFormDefault="qualified"
6 attributeFormDefault="unqualified">
7
8 <xsd:simpleType name="PropertyType">
9 <xsd:annotation>
10 <xsd:documentation>Вид на имот
11 </xsd:documentation>
12 </xsd:annotation>
13 <xsd:restriction base="xsd:string">
14 <xsd:enumeration value="R-0040"/>
15 <xsd:enumeration value="R-0041"/>
16 <xsd:enumeration value="R-0042"/>
17 </xsd:restriction>
18 </xsd:simpleType>
19 </xsd:schema>
VI. Ограничения в използването на възможни конструкции от XML Schema
1. Не се допуска използването на възможността, предоставена от XML Schema стандарта, за предефиниране на типове чрез употребата на "redefine" елемента от XML Schema.
2. Не се допуска използването на възможностите, предоставени от XML Schema стандарта, за заместване на вече декларирани елементи с други елементи в рамките на дефинираните структури чрез използване на механизма "substitution groups".
3. Не се допуска използването на атрибути, декларирани със стойности по подразбиране (use="optional" default="defaultValue").
4. Не се допуска използването на атрибути, които са декларирани едновременно като опционални и с фиксирани стойности (use="optional" fixed="fixedValue").
5. Не се допуска използването на елементи, декларирани със стойности по подразбиране (default="defaultValue").
6. Не се допуска използването на елементи, декларирани с фиксирани стойности (fixed="fixedValue"). Изключение се прави в случаите, в които не е възможно в конкретен XML документ елементът да бъде използван с празна стойност (например елементът/типът на елемента със сигурност не съдържа празен низ, дефинирано чрез използване на фасета <xsd:minLength value="1"/>).
