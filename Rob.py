# ------------------------------------------------------------
# |                         Imports                          |
# ------------------------------------------------------------


# -------------------------Packages---------------------------
import copy as cp
import math
from time import sleep, perf_counter
import numpy as np
import DRIVE.jointdrive_edit as jd

# Für das Deepcopy der Trajektorienliste
# Für die Berechnung der Periodenlänge, der Hauptiteration
# Für die Rechnungen mit Matritzen
# Für die Rechnungen mit den Matritzen


# -------------------------Py Scripts-------------------------<
import ROB.HexaplotSender as hxpS
import LEG.Leg as Leg
import ZMQ.server as server
import ROB.Config as cn


# Für das Senden der Fußpunkte an die Hexapod-Simulation
# Für die Steuerung der sechs Beine (Dummy-Klasse)
# Für das Starten des Servers auf dem Roboter


class Robot:
    """ Klasse Roboter zur Verarbeitung der Befehle des Controllers und zur Weiterübertragung an die Beine. """

    def __init__(self):
        """
        robot() -> Object

        Konstruktor der Klasse robot()
        """

        self.debug = cn.robot['debug']
        self.simulation = cn.robot['simulation']

        self.height_top = cn.robot['height_top']
        """ Höhe für die Berechnung der Trajektorienpunkte. """

        self.height_bot = cn.robot['height_bot']
        """ Höhe für die Berechnung der Trajektorienpunkte. """
        # ---------------------Class Objects----------------------

        self.sv = server.Server()
        """ Objekt der Klasse Server zum Starten des Servers auf dem Roboter. """

        self.broadcast = jd.JointDrive(id=254)

        # Leg 1
        self.leg_v_r = Leg.Leg(cn.leg_v_r['measures'], cn.leg_v_r['offset'], cn.leg_v_r['rotation'],
                               cn.leg_v_r['motorId'], cn.leg_v_r['angle'], cn.leg_v_r['startup'], cn.leg_v_r['ccw'])
        """ Beinobjekt für das Bein vorne rechts. """

        # Leg 2
        self.leg_v_l = Leg.Leg(cn.leg_v_l['measures'], cn.leg_v_l['offset'], cn.leg_v_l['rotation'],
                               cn.leg_v_l['motorId'], cn.leg_v_l['angle'], cn.leg_v_l['startup'], cn.leg_v_l['ccw'])
        """ Beinobjekt für das Bein vorne links. """

        # Leg 3
        self.leg_m_l = Leg.Leg(cn.leg_m_l['measures'], cn.leg_m_l['offset'], cn.leg_m_l['rotation'],
                               cn.leg_m_l['motorId'], cn.leg_m_l['angle'], cn.leg_m_l['startup'], cn.leg_m_l['ccw'])
        """ Beinobjekt für das Bein mitte links. """

        # leg 4
        self.leg_h_l = Leg.Leg(cn.leg_h_l['measures'], cn.leg_h_l['offset'], cn.leg_h_l['rotation'],
                               cn.leg_h_l['motorId'], cn.leg_h_l['angle'], cn.leg_h_l['startup'], cn.leg_h_l['ccw'])
        """ Beinobjekt für das Bein hinten links. """

        # leg 5
        self.leg_h_r = Leg.Leg(cn.leg_h_r['measures'], cn.leg_h_r['offset'], cn.leg_h_r['rotation'],
                               cn.leg_h_r['motorId'], cn.leg_h_r['angle'], cn.leg_h_r['startup'], cn.leg_h_r['ccw'])
        """ Beinobjekt für das Bein hinten rechts. """

        # Leg 6
        self.leg_m_r = Leg.Leg(cn.leg_m_r['measures'], cn.leg_m_r['offset'], cn.leg_m_r['rotation'],
                               cn.leg_m_r['motorId'], cn.leg_m_r['angle'], cn.leg_m_r['startup'], cn.leg_m_r['ccw'])
        """ Beinobjekt für das Bein mitte rechts. """

        if self.simulation:
            self.sender = hxpS.HexaplotSender()
            """ Objekt der Klasse HexaplotSender zum Senden der Fußpunkte an die Simulation. """

        # --------------------Class Variables----------------------


        self.all_legs = [self.leg_v_r, self.leg_v_l, self.leg_m_l, self.leg_h_l, self.leg_h_r, self.leg_m_r]
        """ Liste mit allen Beinobjekten. """
        self.group_a = [self.leg_v_r, self.leg_m_l, self.leg_h_r]
        """ Liste mit den stemmendenden Beintrio-Objekten. """
        self.group_b = [self.leg_v_l, self.leg_m_r, self.leg_h_l]
        """ Liste mit den schwingenden  Beintrio-Objekten. """

        self.traj = []
        self.traj_triangle = cn.robot['triangle']
        self.traj_rectangle = cn.robot['rectangle']
        self.traj_fast = cn.robot['fast']

        self.cycle_time = cn.robot['cycle_time']
        """ Zykluszeit für die Abfrage auf neue Befehle. (Defaultwert = 400ms) """
        self.speed_max = cn.robot['speed_max']
        """ Geschwindigkeit mit der sich der Roboter bewegen soll. (Defaultgeschwindigkeit = 0.4) """
        self.radius = cn.robot['radius']
        """ Radius vom Arbeitsbereich eines Beines. (Defaultradius = 5cm) """

        if self.simulation:
            lines = []
            for legs in self.all_legs:
                for i in range(1, 4):
                    lines.append([legs.getJointPosition(i)[:-1], legs.getJointPosition(i + 1)[:-1]])
            self.sender.send_points(lines)


    # -------------------------Methods-----------------------------
    def iterate(self):
        """
        iterate() -> None

        Die Hauptmethode, welche auf dem Roboter gestartet wird.
        Diese hat eine Endlosschleife, welche die fortlaufenden Befehle des Benutzers verarbeitet.
        """
        for legs in self.group_a:
            legs.setPosition(legs.getOffset()[:-1] + [-self.height_top, 1])
        for legs in self.group_b:
            legs.setPosition(legs.getOffset()[:-1] + [-self.height_bot, 1])
        self.broadcast.mach()
        if self.simulation:
            lines = []
            for legs in self.all_legs:
                for i in range(1, 4):
                    lines.append([legs.getJointPosition(i)[:-1], legs.getJointPosition(i + 1)[:-1]])
            self.sender.send_points(lines)
        speed = 20
        schwingpunkt = 0
        pace_type = "Dreieck"
        while 1:
            t_start = perf_counter()

            if schwingpunkt == 0 or schwingpunkt == int(len(self.traj) / 2):
                n_commands = self.get_new_commands()
                if schwingpunkt == int(len(self.traj) / 2):
                    if pace_type == "Fast":
                        schwingpunkt = 0
                if n_commands != 0:
                    speed, angle, pace_type = n_commands[0], n_commands[1], n_commands[2].decode('UTF-8')
                    if speed == 0:
                        continue
                    if pace_type == "Rechteck":
                        self.traj = self.traj_rectangle
                        self.traj = self.calc_tray_list(self.traj, length=self.radius, height=cn.robot['height_r'])
                    elif pace_type == "Fast":
                        self.traj = self.traj_fast
                        self.traj = self.calc_tray_list(self.traj, length=self.radius, height=cn.robot['height_f'])
                    else:
                        self.traj = self.traj_triangle
                        self.traj = self.calc_tray_list(self.traj, length=self.radius, height=cn.robot['height_t'])
                    if schwingpunkt != 0:
                        schwingpunkt = int(len(self.traj) / 2)
                    self.traj = self.set_direction(self.traj, angle)
                    if self.debug:
                        print(self.traj)
                    self.traj = self.traj.tolist()
                    speed *= self.speed_max
                else:
                    continue
            elif schwingpunkt == len(self.traj):
                schwingpunkt = 0
                continue
            stemmpunkt = schwingpunkt + len(self.traj) / 2

            if stemmpunkt >= len(self.traj):
                stemmpunkt = stemmpunkt - len(self.traj)

            stemmpunkt = int(stemmpunkt)
            for legs in self.group_a:
                legs.setPosition(self.go_to(legs.getOffset(), self.traj[schwingpunkt]) + [1], speed)
            for legs in self.group_b:
                legs.setPosition(self.go_to(legs.getOffset(), self.traj[stemmpunkt]) + [1], speed)
            self.broadcast.mach()
            if self.simulation:
                lines = []
                for legs in self.all_legs:
                    for i in range(1, 4):
                        lines.append([legs.getJointPosition(i)[:-1], legs.getJointPosition(i + 1)[:-1]])
                self.sender.send_points(lines)

            schwingpunkt += 1
            t_end = perf_counter()
            period_length = t_end - t_start
            sleep(self.cycle_time - period_length)

            if self.debug:
                print(period_length)

    @staticmethod
    def calc_tray_list(org_traj, offset=None, length=1.0, height=1.0):
        """
        calc_tray_list(org_traj: List[List[x: float,y: float,z: float]], offset: tuple(x,y,z), length: float, height: float) -> List()

        Eine Methode zum berechnen einer neuen Trajektorienliste, mit einer anderen Höhe, Länge oder Startposition.
        """

        traj = cp.deepcopy(org_traj)
        if offset is None:
            offset = [0, 0, 0]
        for point in traj:
            point[0] = point[0] * length + offset[0]
            point[1] = point[1] * length + offset[1]
            point[2] = point[2] * height + offset[2]
        return traj

    @staticmethod
    def rotation_z(teta):
        """
        rotation_z(teta: float) -> numpy.matrix()

        Eine statische Methode zum berechnen einer Rotationsmatrix um die Z-Achse, mit dem Winkel Teta
        """
        rz_matrix = np.matrix([[math.cos(teta), -1 * math.sin(teta), 0],
                               [math.sin(teta), math.cos(teta), 0],
                               [0, 0, 1]])
        return rz_matrix

    def set_direction(self, org_traj, angle):
        """
        set_direction(org_traj: List(), angle: float) -> numpy.matrix()

        Eine Methode zum berechnen der neuen Trajektorienliste, verschoben um die z-Achse mit der Variable Angle.
        """
        traj = np.matrix(cp.deepcopy(org_traj))
        for i in range(0, len(traj)):
            traj[i] = traj[i] * self.rotation_z(angle)
        return traj

    def get_new_commands(self, command=None):
        """
        get_new_commands(command: List[tuple(x: float,y: float),speed: float,pacetype: str]) -> List[tuple(x: float,y: float),speed: float,pacetype: str]

        Eine Methode zum Abfangen der Daten vom Clienten oder auch zum Eingeben eigener Befehle über die Methode
        """
        if not command:
            command = self.sv.get_data()

        if self.debug:
            typ = type(command)
            print(command)
            print(typ)
        return command

    @staticmethod
    def go_to(offset, xyz):
        new_xyz = cp.deepcopy(offset)
        for i in range(0, len(offset)):
            new_xyz[i] += xyz[i]
        return new_xyz


if __name__ == "__main__":
    rob = Robot()
    rob.iterate()
