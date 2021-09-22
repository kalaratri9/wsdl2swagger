import json
import xmltodict
import re
import boto3
import copy

translate = boto3.client(service_name='translate')

notTranslatableWords = ["Array","Status"]
translatedWords = {}

def getTypeDef(element):
    minOccurs = ""
    maxOccurs = ""

    if "@minOccurs" in element.keys():
        minOccurs = ", minOccurs: " + element["@minOccurs"]
    if "@maxOccurs" in element.keys():
        maxOccurs = element["@maxOccurs"]
    typeDef = {}
    if 'xs:' in element['@type']:
        typeStr = element['@type']
        typeStr = typeStr[3:]
        if typeStr == "int":
            typeDef = {"type" : "integer", "format": "int32"}
        elif typeStr == "long":
            typeDef = {"type" : "integer", "format": "int64"}
        elif typeStr == "double":
            typeDef = {"type" : "number", "format": "double"}
        elif typeStr == "float":
            typeDef = {"type" : "number", "format": "float"}
        elif typeStr == "dateTime":
            typeDef = {"type" : "string", "format": "date-time"}
        else:
            typeDef = {"type" : typeStr}
    else:
        typeStr = element['@type']
        typeStr = typeStr[typeStr.index(":")+1:]
        typeStr = "#/definitions/"+typeStr
        if maxOccurs == "unbounded":
            typeDef = {"type":"array","items":{"$ref" : typeStr}}
        else:
            typeDef = {"$ref" : typeStr}
    return typeDef


def translateTerm(stringDef):
#    print(stringDef)
    if len(stringDef) == 0:
        return stringDef
    translatedString = ""
    space = ""
    termToTranslate = ""
    terms = re.findall('[A-Z][^A-Z]*', stringDef)
#    print(terms, " ", len(terms))
    suffix = ""
    if len(terms) > 1:
        for word in terms:
            if word not in ["Response", "Result"]:
                termToTranslate += space + word
                space = " "
            else:
                suffix = word
    else: 
        termToTranslate = stringDef
#    print(termToTranslate)
    if termToTranslate not in translatedWords.keys():
        result = translate.translate_text(Text=termToTranslate, 
            SourceLanguageCode="es", TargetLanguageCode="en")
        translatedTerm = result.get('TranslatedText')
        translatedTerm = translatedTerm.title()
        translatedTerm = translatedTerm.replace(" ","")
        translatedTerm = translatedTerm + suffix
        translatedWords.update({termToTranslate:translatedTerm})
    translatedString=translatedWords[termToTranslate]
#    print(translatedString)
#    print()
    return translatedString

def getComplexTypeObjectDefinition(complexType):
    properties = {}
    elements = complexType['xs:sequence']['xs:element']
    if isinstance(elements,list):
        for element in elements:
            typeDef = getTypeDef(element)
            elementName = element['@name']
            properties.update({elementName: typeDef})
    else:
        typeDef = getTypeDef(elements)
        elementName = elements['@name']
        properties.update({elementName:  typeDef})
    if 'xs:simpleType' in complexType['xs:sequence'].keys():
        simpleTypes = complexType['xs:sequence']['xs:simpleType']
        print(simpleTypes)
    definition = {"type": "object"}
    definition.update({"properties":properties})
    complexTypeName = complexType['@name']
    definition.update({"title":complexTypeName})
    objectDef = {complexTypeName: definition}
    return objectDef


def getElementObjectDefinition(complexType):
    properties = {}
    elements = complexType['xs:sequence']['xs:element']
    if isinstance(elements,list):
        for element in elements:
            typeDef = getTypeDef(element)
            elementName = element['@name']
            properties.update({elementName: typeDef})
    else:
        typeDef = getTypeDef(elements)
        elementName = elements['@name']
        properties.update({elementName:  typeDef})
    if 'xs:simpleType' in complexType['xs:sequence'].keys():
        simpleTypes = complexType['xs:sequence']['xs:simpleType']
        # TODO: Define what to do with these simpleTypes
        #print(simpleTypes)
    definition = {"type": "object"}
    definition.update({"properties":properties})
    return definition

def getDefinitions(schemas):
    definitions = {}
    for schemaDef in schemas:
        if "xs:complexType" in schemaDef.keys():
            complexType = schemaDef["xs:complexType"]
            if isinstance(complexType, dict):
                object = getComplexTypeObjectDefinition(complexType)
                definitions.update(object)
            else:
                for singleComplexType in complexType:
                    object = getComplexTypeObjectDefinition(singleComplexType)
                    definitions.update(object)
        if "xs:simpleType" in schemaDef.keys():
            simpleTypes = schemaDef["xs:simpleType"]
            if isinstance(simpleTypes, dict):
                if simpleTypes["xs:restriction"]["@base"] == "xs:string" and \
                    "xs:enumeration" in simpleTypes["xs:restriction"].keys():
                    enumDef = []
                    for enum in simpleTypes["xs:restriction"]["xs:enumeration"]:
                        enumDef.append(enum["@value"])
                    typeDef = {"type": "string", "enum": enumDef}
                    elementName = simpleTypes["@name"]
                    simpleTypeDef = {elementName: typeDef}
                    definitions.update(simpleTypeDef)
                else:
                    print(simpleTypes["@name"])
                    print(simpleTypes["xs:restriction"]["@base"])
            else:
                for simpleType in simpleTypes:
                    if simpleType["xs:restriction"]["@base"] == "xs:string" and \
                        "xs:enumeration" in simpleType["xs:restriction"].keys():
                        enumDef = []
                        for enum in simpleType["xs:restriction"]["xs:enumeration"]:
                            enumDef.append(enum["@value"])
                        typeDef = {"type": "string", "enum": enumDef}
                        elementName = simpleType["@name"]
                        simpleTypeDef = {elementName: typeDef}
                        definitions.update(simpleTypeDef)
                    else:
                        print(simpleType["@name"])
                        print(simpleType["xs:restriction"]["@base"])
    return definitions

def getElements(schemas, messages,definitions):
    elements = {}
    for schemaDef in schemas:
        if "xs:element" in schemaDef.keys():
            xsElements = schemaDef["xs:element"]
            if isinstance(xsElements, dict):
                elementName = xsElements["@name"]
                if elementName in messages.values():
                    typeDef = getTypeDef(xsElements)
                    elementDef = {elementName: typeDef}
                    if elementName not in definitions.keys():
                        elements.update(elementDef)
            else:
                for singleXsElement in xsElements:
                    elementName = singleXsElement["@name"]
                    if elementName in messages.values():
                        elementObjectDef = getElementObjectDefinition(singleXsElement["xs:complexType"])
                        elementDef = {elementName: elementObjectDef}
                        if elementName not in definitions.keys():
                            elements.update(elementDef)
    return elements

def getMessages(wsdlMessages):
    messages = {}
    for wsdlMessage in wsdlMessages:
        message = {}
        part = wsdlMessage["wsdl:part"]
        elementName = part["@element"]
        elementName = elementName[elementName.index(":")+1:]
        message = {wsdlMessage["@name"]: elementName }
        messages.update(message)
    return messages

def getPaths(wsdlPortType, messages):
    paths = {}
    for wsdlOperation in wsdlPortType["wsdl:operation"]:
        messageName = wsdlOperation["wsdl:input"]["@message"]
        messageName = messageName[messageName.index(":")+1:]
        messageName = messages[messageName]
        referencedObject = "#/definitions/"+messageName
        parameters = [
                {
                    "in": "body",
                    "name": messageName,
                    "description": "",
                    "required": True,
                    "schema": {
                        "$ref": referencedObject
                    }
                }
            ]
        messageName = wsdlOperation["wsdl:output"]["@message"]
        messageName = messageName[messageName.index(":")+1:]
        messageName = messages[messageName]
        referencedObject = "#/definitions/"+messageName
        response200 = {
                "description": "OK",
                "schema": {
                    "$ref": referencedObject
                }  
        }
        messageName = wsdlOperation["wsdl:fault"]["@message"]
        messageName = messageName[messageName.index(":")+1:]
        messageName = messages[messageName]
        referencedObject = "#/definitions/"+messageName
        response500 = {
            "description": "INTERNAL SERVER ERROR",
            "schema": {
                "$ref": referencedObject
            }
        }
        responses = { "200": response200, "500": response500 }
        path = {
            "post":{
                "tags": [
                    wsdlOperation["@name"]
                ],
                "operationId": wsdlOperation["@name"]+"UsingPOST",
                "consumes": [
                    "application/json"
                ],
                "produces": [
                    "application/json"
                ],
                "parameters": parameters,
                "responses": responses
            }
        }
        paths.update({"/"+wsdlOperation["@name"]:path})
    return paths

def getSwagger(portTypeName, paths, definitions):
    swagger = {
        "swagger": "2.0",
            "info": {
                "description": "Documentation for " + portTypeName,
                "version": "1.0",
                "title": portTypeName +" REST services",
                "termsOfService": "Terms of service",
                "license": {
                    "name": ""
                }
            },
            "host": "localhost:8080",
            "basePath": "/"+portTypeName,
            "paths": paths,
            "definitions": definitions
    }
    return swagger

def translateSwagger(swagger):
    newPaths = {}
    for path in swagger["paths"].keys():
        newPath = swagger["paths"][path]
        newPathName = path[1:]
        translatedPathName = "/"+translateTerm(newPathName)
        translatedTag = translateTerm(newPath["post"]["tags"][0])
        newPath["post"]["tags"][0] = translatedTag
        translatedOperationId = translateTerm(newPath["post"]["operationId"])
        newPath["post"]["operationId"] = translatedOperationId
        translatedParameterName = translateTerm(newPath["post"]["parameters"][0]["name"])
        newPath["post"]["parameters"][0]["name"] = translatedParameterName

        schemaName = newPath["post"]["parameters"][0]["schema"]["$ref"]
        schemaName = schemaName[schemaName.rindex("/")+1:]
        translatedSchemaName = "#/definitions/" + translateTerm(schemaName)
        newPath["post"]["parameters"][0]["schema"]["$ref"] = translatedSchemaName

        schemaName = newPath["post"]["responses"]["200"]["schema"]["$ref"]
        schemaName = schemaName[schemaName.rindex("/")+1:]
        translatedSchemaName = "#/definitions/" + translateTerm(schemaName)
        newPath["post"]["responses"]["200"]["schema"]["$ref"] = translatedSchemaName

        schemaName = newPath["post"]["responses"]["500"]["schema"]["$ref"]
        schemaName = schemaName[schemaName.rindex("/")+1:]
        translatedSchemaName = "#/definitions/" + translateTerm(schemaName)
        newPath["post"]["responses"]["500"]["schema"]["$ref"] = translatedSchemaName
        newPaths.update({translatedPathName: newPath})
    swagger["paths"] = newPaths
    translatedDefinitions = {}
    for objectName in swagger["definitions"].keys():        
        translatedObjectName = translateTerm(objectName)
        objectDef = swagger["definitions"][objectName]
        newObjectDef = copy.deepcopy(objectDef)
        if "properties" in objectDef.keys():
            for propertyKey in objectDef["properties"].keys():
                translatedPropertyName = translateTerm(propertyKey)
                translatedProperty = objectDef["properties"][propertyKey]
                if "$ref" in translatedProperty.keys():
                    schemaName = translatedProperty["$ref"]
                    schemaName = schemaName[schemaName.rindex("/")+1:]
                    translatedSchemaName = "#/definitions/" + translateTerm(schemaName)
                    translatedProperty["$ref"] = translatedSchemaName
                elif "items" in translatedProperty.keys():
                    schemaName = translatedProperty["items"]["$ref"]
                    schemaName = schemaName[schemaName.rindex("/")+1:]
                    translatedSchemaName = "#/definitions/" + translateTerm(schemaName)
                    translatedProperty["items"]["$ref"] = translatedSchemaName                                
                newObjectDef["properties"][translatedPropertyName] = translatedProperty
                del newObjectDef["properties"][propertyKey]
        newObjectDef["title"] = translatedObjectName
        newObject = {translatedObjectName:newObjectDef}
        translatedDefinitions.update(newObject)
    swagger["definitions"] = translatedDefinitions
    return swagger

with open('Cust_single.wsdl', 'r') as file:
    data = file.read().replace('\n', '')

obj = xmltodict.parse(data)
definitions = getDefinitions(obj["wsdl:definitions"]["wsdl:types"]["xs:schema"])
messages = getMessages(obj["wsdl:definitions"]["wsdl:message"])
elements = getElements(obj["wsdl:definitions"]["wsdl:types"]["xs:schema"],messages,definitions)
definitions.update(elements)
paths = getPaths(obj["wsdl:definitions"]["wsdl:portType"],messages)
swagger = getSwagger(obj["wsdl:definitions"]["wsdl:portType"]["@name"],paths, definitions)
swagger = translateSwagger(swagger)
print(json.dumps(swagger))