import functools
import itertools
import json
from urllib.parse import parse_qs

import utils


def handleMissions(environ, start_response):
    c = utils.getCursor()

    o = parse_qs(environ['QUERY_STRING'])

    query, params = constructQuery(o)
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

        c.execute(str.format('''SELECT * FROM comments WHERE missionId IN ({}) ORDER BY missionId''', idParameter))

        commentsFromDb = c.fetchall()
        # group the comments by their mission Id
        commentsGroupedByMission = {}

        for k, g in itertools.groupby(commentsFromDb, lambda x: x['missionId']):
            commentsGroupedByMission[k] = list(g)

    else:
        versionsGroupedByMission = []
        commentsGroupedByMission = []

    user = environ['user']

    # transform the row objects into objects that can be serialized
    m = [toDto(x, versionsGroupedByMission, commentsGroupedByMission, user) for x in missionsFromDb]
    encode = json.dumps(m).encode()

    start_response("200 OK", [])
    return [encode]


def addPermissions(version, movePermission, editPermission):
    version['allowedToMove'] = movePermission
    version['allowedToEdit'] = editPermission
    return version


# copy the variables out of the non-serializable db object into a blank object
def toDto(missionFromDb, verionsGrouped, commentsGrouped, user: utils.User):
    dto = toDtoHelper(missionFromDb)
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

        if dto['id'] in commentsGrouped:
            commentsForThisMission = [toDtoHelper(comment) for comment in commentsGrouped[dto['id']]]
            for comment in commentsForThisMission:
                comment['isComment'] = True
            unsortedData = versionsForThisMission + commentsForThisMission
        else:
            unsortedData = versionsForThisMission

        finalData = sorted(unsortedData, key=functools.cmp_to_key(cmpVersionAndComents))
        dto['versions'] = finalData

    return dto


# version 1 before version 2
# comment 1 before comment 2
# comment with version 1 after version 1, but before version 2
def cmpVersionAndComents(one, two):
    if 'isComment' in one:
        if 'isComment' in two:
            # both comments
            if one['versionId'] == two['versionId']:
                # both comments, and same version, sort by commentId
                return 1 if one['id'] > two['id'] else -1
            else:
                # both comments, but different versions, sort by versionId
                return 1 if one['versionId'] > two['versionId'] else -1
        else:
            # one is a comment, but two is not, sort by versionId
            return 1 if one['versionId'] >= two['id'] else -1
    else:
        if 'isComment' in two:
            # one is not a comment, two is
            return 1 if one['id'] >= two['versionId'] else -1
        else:
            # neither is a comment
            return 1 if one['id'] > two['id'] else -1




def toDtoHelper(version):
    return dict(version)


def constructQuery(params):
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
    return " AND ".join(query), p
