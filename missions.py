import itertools
import json
from urllib.parse import parse_qs

import utils


def handleMissions(environ, start_response):
    c = utils.getCursor()

    o = parse_qs(environ['QUERY_STRING'])

    missionIds = None
    if "new" in o:
        fancyQuery = "select missionId from versions join missions on versions.missionId = missions.id where (versions.createDate > missions.lastPlayed or missions.lastPlayed is null) and existsOnMain = 1 and tobeDeletedMain = 0"
        c.execute(fancyQuery)
        missionIds = c.fetchall()
    if "needsTransfer" in o:
        fancyQuery = "select missionId from versions where existsOnMain = 0 and existsOnMM = 1 and toBeDeletedMM = 0"
        c.execute(fancyQuery)
        missionIds = c.fetchall()

    query, params = constructQuery(o, missionIds)
    # retrieve all the missions that match our parameters

    c.execute("select * from missions where " + query, params)
    missionsFromDb = c.fetchall()

    # if any missions were returned, return all versions associated with those missions
    if len(missionsFromDb) > 0:
        ids = [str(x['id']) for x in missionsFromDb]
        # sqlite can't take lists, so we need to transform it into a string
        #    then format the string into the query so that it doesn't get treated as a string
        idParameter = ",".join(ids)

        c.execute(str.format('''select * from versions where missionId in ({}) order by missionId''', idParameter))
        versionsFromDb = c.fetchall()
        # group the mission by their mission Id
        versionsGroupedByMission = {}
        for k, g in itertools.groupby(versionsFromDb, lambda x: x['missionId']):
            versionsGroupedByMission[k] = list(g)
    else:
        versionsGroupedByMission = []


    user = environ['user']

    # transform the row objects into objects that can be serialized
    m = [toDto(x, versionsGroupedByMission, user) for x in missionsFromDb]
    encode = json.dumps(m).encode()

    start_response("200 OK", [])
    return [encode]


def addPermissions(version, movePermission, editPermission):
    version['allowedToMove'] = movePermission
    version['allowedToEdit'] = editPermission
    return version

# copy the variables out of the non-serializable db object into a blank object
def toDto(missionFromDb, verionsGrouped, user: utils.User):
    dto = toDtoHelper(missionFromDb)
    dto['missionAuthor'] = (dto['missionAuthor'][:8] + '..') if len(dto['missionAuthor']) > 8 else dto['missionAuthor']
    dto['allowedToEdit'] = False
    dto['allowedToVersion'] = False
    allowedToMove = False
    allowedToEdit = False
    if user is not None:
        allowedToEdit = user.permissionLevel >= 2 or user.login in missionFromDb['missionAuthor'].split(",")
        allowedToMove = user.permissionLevel >= 2 or (
        user.login in missionFromDb['missionAuthor'].split(",") and user.permissionLevel >= 1)
        dto['allowedToEdit'] = allowedToEdit
    if dto['id'] in verionsGrouped:
        versionsForThisMission = [toDtoHelper(version) for version in verionsGrouped[dto['id']]]
        versionsForThisMission = [addPermissions(version, allowedToMove, allowedToEdit) for version in
                                  versionsForThisMission]
        finalVersion = sorted(versionsForThisMission, key=lambda x: x['createDate'])
        dto['versions'] = finalVersion

    return dto


def toDtoHelper(version):
    return dict(version)


def constructQuery(params, missionIds: list):
    query = []
    p = []
    if ("map" in params) and (params['map'][0] != 'All Maps'):
        query.append('missionMap = ?')
        p.append(params['map'][0])
    if ("author" in params) and (params['author'][0] != 'All Authors'):
        query.append("missionAuthor = ?")
        p.append(params['author'][0])
    if "status" in params and (params['status'][0] != 'All Statuses'):
        query.append("status = ?")
        p.append(params['status'][0])
    if "missionTypes[]" in params:
        missionTypeString = ["'{0}'".format(w) for w in params['missionTypes[]']]
        query.append(str.format("missionType in({})", ",".join(missionTypeString)))
    if "name" in params:
        query.append("missionName  like ?")
        p.append("%" + params['name'][0] + "%")
    if "playerMax" in params:
        query.append("missionPlayers  <= ? ")
        p.append(params['playerMax'][0])
    if "playerMin" in params:
        query.append("missionPlayers  >= ? ")
        p.append(params['playerMin'][0])
    if "missionId" in params:
        query.append("id  = ? ")
        p.append(params['missionId'][0])
    if missionIds is not None:
        missionIdString = ["'{0}'".format(w['missionId']) for w in missionIds]
        query.append(str.format("id in({})", ",".join(missionIdString)))
    return " AND ".join(query), p
